"""
Retriever nodes — advanced retrieval strategies beyond basic vector search.

Nodes:
  retriever.vector_store          — standard vector similarity search
  retriever.hyde                  — HyDE: generate hypothetical doc, then search
  retriever.multi_query           — generate N queries, merge results
  retriever.cohere_rerank         — Cohere Rerank API post-processing
  retriever.jina_rerank           — Jina Reranker API post-processing
  retriever.voyageai_rerank       — VoyageAI reranker post-processing
  retriever.embeddings_filter     — filter by embedding similarity threshold
  retriever.similarity_threshold  — filter results below a score threshold
  retriever.llm_filter            — LLM judges each document's relevance
  retriever.extract_metadata      — extract metadata from docs via LLM
  retriever.multi_query_merge     — union + deduplicate from multiple retrievers
  retriever.contextual_compression — compress docs to relevant content via LLM
  retriever.parent_document       — retrieve parent doc for matched child chunk
  retriever.rrfusion              — Reciprocal Rank Fusion across result lists
"""
import json
import re
from typing import Any

import httpx
import structlog

from core.config import settings
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


async def _embed(text: str, provider: str = "openai", model: str = "text-embedding-3-small") -> list[float]:
    if provider == "openai":
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OPENAI_API_KEY required for embeddings")
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "input": text},
            )
            r.raise_for_status()
            return r.json()["data"][0]["embedding"]
    raise ValueError(f"Unsupported embed provider: {provider}")


async def _vector_search(query: str, collection: str, top_k: int, db, embed_provider: str = "openai") -> list[dict]:
    from sqlalchemy import text as sqltxt
    vec = await _embed(query, embed_provider)
    vec_str = "[" + ",".join(str(v) for v in vec) + "]"
    sql = sqltxt("""
        SELECT id, content, metadata, 1 - (embedding <=> :vec::vector) AS score
        FROM vector_documents
        WHERE collection_name = :coll
        ORDER BY embedding <=> :vec::vector
        LIMIT :k
    """)
    result = await db.execute(sql, {"vec": vec_str, "coll": collection, "k": top_k})
    rows = result.fetchall()
    return [{"id": str(r[0]), "content": r[1], "metadata": r[2] or {}, "score": float(r[3])} for r in rows]


async def _llm_call(prompt: str, provider: str = "openai", model: str = "gpt-4o-mini",
                    temperature: float = 0.0, max_tokens: int = 512) -> str:
    if provider == "openai":
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OPENAI_API_KEY required")
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}],
                      "temperature": temperature, "max_tokens": max_tokens},
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
    raise ValueError(f"Unsupported provider: {provider}")


# ─── retriever.vector_store ──────────────────────────────────────────────────

@register_node("retriever.vector_store")
async def retriever_vector_store(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Standard vector similarity retrieval."""
    collection = config.get("collection", "default")
    top_k = int(config.get("top_k", 4))
    query = input_data.get("query") or input_data.get("input", "")
    embed_provider = config.get("embed_provider", "openai")
    score_threshold = float(config.get("score_threshold", 0.0))

    docs = await _vector_search(query, collection, top_k, db, embed_provider)
    if score_threshold > 0:
        docs = [d for d in docs if d["score"] >= score_threshold]
    return {"documents": docs, "count": len(docs), "query": query}


# ─── retriever.hyde ──────────────────────────────────────────────────────────

@register_node("retriever.hyde")
async def retriever_hyde(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    HyDE (Hypothetical Document Embeddings): LLM generates a hypothetical
    answer document, then searches using that document's embedding.
    """
    collection = config.get("collection", "default")
    top_k = int(config.get("top_k", 4))
    provider = config.get("provider", "openai")
    model = config.get("model", "gpt-4o-mini")
    embed_provider = config.get("embed_provider", "openai")
    query = input_data.get("query") or input_data.get("input", "")

    hyde_prompt = (
        f"Write a hypothetical document that would be the perfect answer to this question: {query}\n\n"
        f"Hypothetical document:"
    )
    hypothetical_doc = await _llm_call(hyde_prompt, provider, model, 0.5, 512)
    docs = await _vector_search(hypothetical_doc, collection, top_k, db, embed_provider)
    return {"documents": docs, "count": len(docs), "query": query, "hypothetical_doc": hypothetical_doc}


# ─── retriever.multi_query ───────────────────────────────────────────────────

@register_node("retriever.multi_query")
async def retriever_multi_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Generate N query variations with LLM, retrieve for each, then merge unique results.
    """
    collection = config.get("collection", "default")
    top_k = int(config.get("top_k", 3))
    n_queries = int(config.get("n_queries", 3))
    provider = config.get("provider", "openai")
    model = config.get("model", "gpt-4o-mini")
    query = input_data.get("query") or input_data.get("input", "")

    gen_prompt = (
        f"Generate {n_queries} different versions of the following question to retrieve relevant documents. "
        f"Return one question per line.\n\nOriginal question: {query}\n\nVariations:"
    )
    variations_text = await _llm_call(gen_prompt, provider, model, 0.7, 256)
    variations = [q.strip() for q in variations_text.strip().split("\n") if q.strip()][:n_queries]
    if not variations:
        variations = [query]

    seen_ids: set[str] = set()
    all_docs: list[dict] = []
    for q in variations:
        docs = await _vector_search(q, collection, top_k, db)
        for d in docs:
            if d["id"] not in seen_ids:
                seen_ids.add(d["id"])
                all_docs.append(d)

    # Sort by score descending
    all_docs.sort(key=lambda d: d.get("score", 0), reverse=True)
    return {"documents": all_docs[:top_k * 2], "count": len(all_docs), "query_variations": variations}


# ─── retriever.cohere_rerank ─────────────────────────────────────────────────

@register_node("retriever.cohere_rerank")
async def retriever_cohere_rerank(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Retrieve then rerank with Cohere Rerank API.
    config: collection, top_k, rerank_top_n, model
    """
    collection = config.get("collection", "default")
    top_k = int(config.get("top_k", 10))
    rerank_top_n = int(config.get("rerank_top_n", 4))
    cohere_model = config.get("model", "rerank-english-v3.0")
    query = input_data.get("query") or input_data.get("input", "")

    api_key = settings.COHERE_API_KEY
    if not api_key:
        raise ValueError("retriever.cohere_rerank requires COHERE_API_KEY")

    # First retrieve
    docs = await _vector_search(query, collection, top_k, db)
    if not docs:
        return {"documents": [], "count": 0, "query": query}

    # Rerank
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(
            "https://api.cohere.ai/v1/rerank",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": cohere_model,
                "query": query,
                "documents": [d["content"][:512] for d in docs],
                "top_n": rerank_top_n,
            },
        )
        r.raise_for_status()
        results = r.json().get("results", [])

    reranked = []
    for res in results:
        idx = res["index"]
        doc = dict(docs[idx])
        doc["rerank_score"] = res["relevance_score"]
        reranked.append(doc)

    return {"documents": reranked, "count": len(reranked), "query": query, "reranker": "cohere"}


# ─── retriever.jina_rerank ───────────────────────────────────────────────────

@register_node("retriever.jina_rerank")
async def retriever_jina_rerank(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Retrieve then rerank with Jina Reranker API."""
    collection = config.get("collection", "default")
    top_k = int(config.get("top_k", 10))
    rerank_top_n = int(config.get("rerank_top_n", 4))
    jina_model = config.get("model", "jina-reranker-v2-base-multilingual")
    query = input_data.get("query") or input_data.get("input", "")

    api_key = getattr(settings, "JINA_API_KEY", "") or config.get("api_key", "")
    if not api_key:
        raise ValueError("retriever.jina_rerank requires JINA_API_KEY")

    docs = await _vector_search(query, collection, top_k, db)
    if not docs:
        return {"documents": [], "count": 0, "query": query}

    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(
            "https://api.jina.ai/v1/rerank",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": jina_model,
                "query": query,
                "documents": [d["content"][:512] for d in docs],
                "top_n": rerank_top_n,
            },
        )
        r.raise_for_status()
        results = r.json().get("results", [])

    reranked = []
    for res in results:
        idx = res["index"]
        doc = dict(docs[idx])
        doc["rerank_score"] = res.get("relevance_score", 0)
        reranked.append(doc)

    return {"documents": reranked, "count": len(reranked), "query": query, "reranker": "jina"}


# ─── retriever.voyageai_rerank ───────────────────────────────────────────────

@register_node("retriever.voyageai_rerank")
async def retriever_voyageai_rerank(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Retrieve then rerank with VoyageAI reranker."""
    collection = config.get("collection", "default")
    top_k = int(config.get("top_k", 10))
    rerank_top_n = int(config.get("rerank_top_n", 4))
    voyage_model = config.get("model", "rerank-1")
    query = input_data.get("query") or input_data.get("input", "")

    api_key = getattr(settings, "VOYAGE_API_KEY", "") or config.get("api_key", "")
    if not api_key:
        raise ValueError("retriever.voyageai_rerank requires VOYAGE_API_KEY")

    docs = await _vector_search(query, collection, top_k, db)
    if not docs:
        return {"documents": [], "count": 0, "query": query}

    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(
            "https://api.voyageai.com/v1/rerank",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": voyage_model,
                "query": query,
                "documents": [d["content"][:512] for d in docs],
                "top_k": rerank_top_n,
            },
        )
        r.raise_for_status()
        results = r.json().get("data", [])

    reranked = []
    for res in sorted(results, key=lambda x: x.get("relevance_score", 0), reverse=True):
        idx = res["index"]
        doc = dict(docs[idx])
        doc["rerank_score"] = res.get("relevance_score", 0)
        reranked.append(doc)

    return {"documents": reranked, "count": len(reranked), "query": query, "reranker": "voyageai"}


# ─── retriever.embeddings_filter ─────────────────────────────────────────────

@register_node("retriever.embeddings_filter")
async def retriever_embeddings_filter(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Retrieve, then filter documents by cosine similarity to query embedding.
    config: collection, top_k, similarity_threshold, embed_provider
    """
    import math
    collection = config.get("collection", "default")
    top_k = int(config.get("top_k", 10))
    threshold = float(config.get("similarity_threshold", 0.76))
    embed_provider = config.get("embed_provider", "openai")
    query = input_data.get("query") or input_data.get("input", "")

    docs = await _vector_search(query, collection, top_k * 2, db, embed_provider)
    filtered = [d for d in docs if d.get("score", 0) >= threshold]

    return {"documents": filtered[:top_k], "count": len(filtered), "query": query,
            "threshold": threshold, "pre_filter_count": len(docs)}


# ─── retriever.similarity_threshold ──────────────────────────────────────────

@register_node("retriever.similarity_threshold")
async def retriever_similarity_threshold(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Filter retrieved documents to those above a similarity score threshold."""
    collection = config.get("collection", "default")
    top_k = int(config.get("top_k", 20))
    threshold = float(config.get("score_threshold", 0.7))
    query = input_data.get("query") or input_data.get("input", "")

    docs = await _vector_search(query, collection, top_k, db)
    filtered = [d for d in docs if d.get("score", 0) >= threshold]

    return {"documents": filtered, "count": len(filtered), "query": query, "threshold": threshold}


# ─── retriever.llm_filter ────────────────────────────────────────────────────

@register_node("retriever.llm_filter")
async def retriever_llm_filter(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Retrieve then use LLM to judge each document's relevance.
    config: collection, top_k, provider, model, filter_prompt
    """
    collection = config.get("collection", "default")
    top_k = int(config.get("top_k", 8))
    provider = config.get("provider", "openai")
    model = config.get("model", "gpt-4o-mini")
    query = input_data.get("query") or input_data.get("input", "")
    filter_prompt_tmpl = config.get(
        "filter_prompt",
        "Is the following document relevant to the question? Answer only YES or NO.\n\n"
        "Question: {query}\n\nDocument: {document}\n\nRelevant (YES/NO):"
    )

    docs = await _vector_search(query, collection, top_k, db)
    relevant = []
    for doc in docs:
        prompt = filter_prompt_tmpl.replace("{query}", query).replace("{document}", doc["content"][:500])
        answer = await _llm_call(prompt, provider, model, 0.0, 10)
        if "YES" in answer.upper():
            doc["llm_relevant"] = True
            relevant.append(doc)

    return {"documents": relevant, "count": len(relevant), "query": query,
            "original_count": len(docs), "filtered_count": len(docs) - len(relevant)}


# ─── retriever.extract_metadata ──────────────────────────────────────────────

@register_node("retriever.extract_metadata")
async def retriever_extract_metadata(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Retrieve documents, then extract specified metadata fields via LLM.
    config: collection, top_k, metadata_schema (list of {key, description}), provider, model
    """
    collection = config.get("collection", "default")
    top_k = int(config.get("top_k", 4))
    metadata_schema = config.get("metadata_schema", [{"key": "topic", "description": "the main topic"}])
    provider = config.get("provider", "openai")
    model = config.get("model", "gpt-4o-mini")
    query = input_data.get("query") or input_data.get("input", "")

    docs = await _vector_search(query, collection, top_k, db)
    schema_desc = "; ".join(f"{s['key']}: {s['description']}" for s in metadata_schema)

    enriched = []
    for doc in docs:
        extract_prompt = (
            f"Extract the following fields from the document. Return as JSON.\n"
            f"Fields: {schema_desc}\n\nDocument:\n{doc['content'][:1000]}\n\nJSON:"
        )
        extracted_text = await _llm_call(extract_prompt, provider, model, 0.0, 256)
        try:
            m = re.search(r"\{.*\}", extracted_text, re.DOTALL)
            extracted = json.loads(m.group()) if m else {}
        except Exception:
            extracted = {}
        new_doc = dict(doc)
        new_doc["extracted_metadata"] = extracted
        new_doc["metadata"] = {**doc.get("metadata", {}), **extracted}
        enriched.append(new_doc)

    return {"documents": enriched, "count": len(enriched), "query": query}


# ─── retriever.contextual_compression ────────────────────────────────────────

@register_node("retriever.contextual_compression")
async def retriever_contextual_compression(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Retrieve documents, then compress each to only include content relevant to the query.
    """
    collection = config.get("collection", "default")
    top_k = int(config.get("top_k", 4))
    provider = config.get("provider", "openai")
    model = config.get("model", "gpt-4o-mini")
    query = input_data.get("query") or input_data.get("input", "")

    docs = await _vector_search(query, collection, top_k, db)
    compressed = []
    for doc in docs:
        compress_prompt = (
            f"Given the following document and a question, extract only the sentences "
            f"from the document that are directly relevant to the question. "
            f"If no content is relevant, respond with 'NOT RELEVANT'.\n\n"
            f"Question: {query}\n\nDocument:\n{doc['content'][:2000]}\n\nRelevant content:"
        )
        extracted = await _llm_call(compress_prompt, provider, model, 0.0, 512)
        if "NOT RELEVANT" not in extracted.upper():
            new_doc = dict(doc)
            new_doc["original_content"] = doc["content"]
            new_doc["content"] = extracted.strip()
            compressed.append(new_doc)

    return {"documents": compressed, "count": len(compressed), "query": query,
            "original_count": len(docs)}


# ─── retriever.rrfusion ──────────────────────────────────────────────────────

@register_node("retriever.rrfusion")
async def retriever_rrfusion(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Reciprocal Rank Fusion (RRF) across multiple query result lists.
    Generates N query variations, retrieves for each, fuses rankings.
    config: collection, top_k, n_queries, k_rrf, provider, model
    """
    collection = config.get("collection", "default")
    top_k = int(config.get("top_k", 4))
    n_queries = int(config.get("n_queries", 3))
    k_rrf = int(config.get("k_rrf", 60))  # RRF constant
    provider = config.get("provider", "openai")
    model = config.get("model", "gpt-4o-mini")
    query = input_data.get("query") or input_data.get("input", "")

    # Generate query variations
    gen_prompt = (
        f"Generate {n_queries} different search queries to find information about: {query}\n"
        f"Return one query per line, no numbering:"
    )
    variations_text = await _llm_call(gen_prompt, provider, model, 0.7, 256)
    queries = [q.strip() for q in variations_text.strip().split("\n") if q.strip()][:n_queries]
    if not queries:
        queries = [query]

    # Collect ranked lists
    doc_scores: dict[str, float] = {}
    doc_store: dict[str, dict] = {}
    for q in queries:
        results = await _vector_search(q, collection, top_k * 2, db)
        for rank, doc in enumerate(results):
            doc_id = doc["id"]
            rrf_score = 1.0 / (k_rrf + rank + 1)
            doc_scores[doc_id] = doc_scores.get(doc_id, 0.0) + rrf_score
            doc_store[doc_id] = doc

    # Sort by RRF score
    fused = sorted(
        [{"rrf_score": score, **doc_store[doc_id]} for doc_id, score in doc_scores.items()],
        key=lambda x: x["rrf_score"],
        reverse=True,
    )
    return {"documents": fused[:top_k], "count": min(len(fused), top_k), "query": query,
            "queries_used": queries, "method": "rrf"}
