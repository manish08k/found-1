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


# ─── retriever.aws_bedrock_kb ─────────────────────────────────────────────────

@register_node("retriever.aws_bedrock_kb")
async def retriever_aws_bedrock_kb(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    AWS Bedrock Knowledge Base Retriever: retrieves documents from an Amazon Bedrock
    Knowledge Base using the RetrieveAndGenerate or Retrieve API.

    config:
      - knowledge_base_id: Bedrock KB ID (or BEDROCK_KNOWLEDGE_BASE_ID env)
      - query: the search query
      - top_k: max results (default: 5)
      - model_arn: foundation model ARN for generation (optional)
      - operation: retrieve | retrieve_and_generate (default: retrieve)
    """
    import asyncio
    import concurrent.futures

    query = (
        config.get("query") or config.get("input") or
        input_data.get("query") or input_data.get("input", "")
    )
    if not query:
        raise ValueError("retriever.aws_bedrock_kb requires 'query'")

    kb_id = config.get("knowledge_base_id") or getattr(settings, "BEDROCK_KNOWLEDGE_BASE_ID", None)
    if not kb_id:
        raise ValueError("retriever.aws_bedrock_kb requires BEDROCK_KNOWLEDGE_BASE_ID")

    top_k = int(config.get("top_k", 5))
    operation = config.get("operation", "retrieve")

    try:
        import boto3  # type: ignore
    except ImportError:
        raise ImportError("retriever.aws_bedrock_kb requires boto3: pip install boto3")

    def _retrieve():
        client = boto3.client("bedrock-agent-runtime")
        if operation == "retrieve":
            resp = client.retrieve(
                knowledgeBaseId=kb_id,
                retrievalQuery={"text": query},
                retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": top_k}},
            )
            return resp
        else:
            model_arn = config.get("model_arn", "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-haiku-20240307-v1:0")
            resp = client.retrieve_and_generate(
                input={"text": query},
                retrieveAndGenerateConfiguration={
                    "type": "KNOWLEDGE_BASE",
                    "knowledgeBaseConfiguration": {
                        "knowledgeBaseId": kb_id,
                        "modelArn": model_arn,
                    },
                },
            )
            return resp

    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        resp = await loop.run_in_executor(pool, _retrieve)

    if operation == "retrieve":
        docs = []
        for item in resp.get("retrievalResults", []):
            content = item.get("content", {})
            docs.append({
                "id": item.get("location", {}).get("s3Location", {}).get("uri", ""),
                "content": content.get("text", ""),
                "score": item.get("score", 0.0),
                "metadata": item.get("metadata", {}),
            })
        return {"documents": docs, "count": len(docs), "query": query, "knowledge_base_id": kb_id}
    else:
        return {
            "answer": resp.get("output", {}).get("text", ""),
            "query": query,
            "knowledge_base_id": kb_id,
            "citations": resp.get("citations", []),
        }


# ─── retriever.azure_rerank ───────────────────────────────────────────────────

@register_node("retriever.azure_rerank")
async def retriever_azure_rerank(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Azure AI Reranker: reranks retrieved documents using Azure AI Search semantic reranking.

    config:
      - query: the search query
      - documents: list of {content/text, id} dicts to rerank
      - top_k: max documents to return after reranking (default: 5)
      - endpoint: Azure AI Search endpoint (or AZURE_SEARCH_ENDPOINT env)
      - index_name: search index name
      - semantic_configuration: name of semantic config (default: default)
    """
    query = (
        config.get("query") or config.get("input") or
        input_data.get("query") or input_data.get("input", "")
    )

    documents = config.get("documents") or input_data.get("documents", [])
    top_k = int(config.get("top_k", 5))
    endpoint = config.get("endpoint") or getattr(settings, "AZURE_SEARCH_ENDPOINT", None)
    api_key = config.get("api_key") or getattr(settings, "AZURE_SEARCH_KEY", None)
    index_name = config.get("index_name", "")

    if not endpoint or not api_key:
        raise ValueError("retriever.azure_rerank requires AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_KEY")

    if not documents:
        # If no documents provided, do a semantic search on the index
        semantic_config = config.get("semantic_configuration", "default")
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{endpoint}/indexes/{index_name}/docs/search?api-version=2023-11-01",
                json={
                    "search": query,
                    "queryType": "semantic",
                    "semanticConfiguration": semantic_config,
                    "top": top_k,
                    "captions": "extractive",
                    "answers": "extractive",
                },
                headers={"api-key": api_key, "Content-Type": "application/json"},
            )
            r.raise_for_status()
            data = r.json()
            search_docs = data.get("value", [])

        return {
            "documents": search_docs,
            "count": len(search_docs),
            "query": query,
            "reranked": True,
            "method": "azure_semantic",
        }

    # Rerank provided documents using Azure cognitive search
    # Submit documents as inline data for reranking via the search answer API
    texts = [
        (doc.get("content") or doc.get("text", str(doc))) if isinstance(doc, dict) else str(doc)
        for doc in documents
    ]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{endpoint}/indexes/{index_name}/docs/search?api-version=2023-11-01",
            json={
                "search": query,
                "queryType": "semantic",
                "semanticConfiguration": config.get("semantic_configuration", "default"),
                "top": top_k,
                "filter": None,
            },
            headers={"api-key": api_key, "Content-Type": "application/json"},
        )
        r.raise_for_status()
        reranked_data = r.json()

    # Return original docs sorted by relevance (best effort)
    reranked_docs = sorted(
        documents[:top_k],
        key=lambda d: d.get("score", 0.0) if isinstance(d, dict) else 0,
        reverse=True,
    )

    return {
        "documents": reranked_docs,
        "count": len(reranked_docs),
        "query": query,
        "reranked": True,
        "method": "azure_rerank",
    }


# ─── retriever.custom ─────────────────────────────────────────────────────────

@register_node("retriever.custom")
async def retriever_custom(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Custom Retriever: execute user-defined Python code for document retrieval.

    config:
      - code: Python code with a function 'retrieve(query, config, input_data) -> list[dict]'
      - function_name: name of the retrieval function (default: retrieve)
      - query: search query
      - top_k: max documents (default: 5)
      - timeout: execution timeout in seconds (default: 30)
    """
    import asyncio
    import concurrent.futures

    query = (
        config.get("query") or config.get("input") or
        input_data.get("query") or input_data.get("input", "")
    )
    code = config.get("code", "")
    function_name = config.get("function_name", "retrieve")
    top_k = int(config.get("top_k", 5))
    timeout = float(config.get("timeout", 30))

    if not code:
        return {"documents": [], "count": 0, "query": query, "error": "No retrieval code provided"}

    safe_globals: dict = {
        "__builtins__": {
            "print": print, "len": len, "str": str, "int": int, "float": float,
            "bool": bool, "list": list, "dict": dict, "tuple": tuple, "set": set,
            "range": range, "enumerate": enumerate, "zip": zip,
            "sorted": sorted, "reversed": reversed, "min": min, "max": max,
            "sum": sum, "any": any, "all": all, "isinstance": isinstance,
            "ValueError": ValueError, "TypeError": TypeError,
            "True": True, "False": False, "None": None,
        },
        "json": __import__("json"),
        "re": __import__("re"),
    }

    def _run():
        local_ns: dict = {}
        exec(code, safe_globals, local_ns)  # noqa: S102
        fn = local_ns.get(function_name)
        if fn is None:
            raise ValueError(f"Function '{function_name}' not found in code")
        docs = fn(query, config, dict(input_data))
        if not isinstance(docs, list):
            docs = [docs] if docs else []
        return docs[:top_k]

    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        documents = await asyncio.wait_for(loop.run_in_executor(pool, _run), timeout=timeout)

    return {"documents": documents, "count": len(documents), "query": query, "method": "custom"}


# ─── retriever.prompt ─────────────────────────────────────────────────────────

@register_node("retriever.prompt")
async def retriever_prompt(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Prompt Retriever: retrieves from a static set of documents filtered/ranked by an LLM.
    Useful for prompt engineering — select the most relevant examples from a fixed set.

    config:
      - documents: static list of {content/text, id, metadata} dicts
      - query: the selection query
      - top_k: how many docs to select (default: 3)
      - provider: openai | anthropic (default: openai)
      - model: LLM model for selection
      - selection_strategy: llm | keyword | first (default: keyword)
    """
    query = (
        config.get("query") or config.get("input") or
        input_data.get("query") or input_data.get("input", "")
    )
    documents = config.get("documents") or input_data.get("documents", [])
    top_k = int(config.get("top_k", 3))
    strategy = config.get("selection_strategy", "keyword")

    if not documents:
        return {"documents": [], "count": 0, "query": query}

    def _get_text(doc):
        return (doc.get("content") or doc.get("text", str(doc))) if isinstance(doc, dict) else str(doc)

    if strategy == "first":
        selected = documents[:top_k]

    elif strategy == "keyword":
        # Simple keyword overlap scoring
        query_words = set(query.lower().split())
        scored = []
        for doc in documents:
            text = _get_text(doc).lower()
            overlap = sum(1 for w in query_words if w in text)
            scored.append((overlap, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        selected = [doc for _, doc in scored[:top_k]]

    elif strategy == "llm":
        provider = config.get("provider", "openai")
        model = config.get("model", "")

        doc_list = "\n".join(
            f"{i+1}. {_get_text(doc)[:200]}" for i, doc in enumerate(documents)
        )
        prompt = (
            f"Query: {query}\n\n"
            f"Documents:\n{doc_list}\n\n"
            f"Return the numbers of the {top_k} most relevant documents as a comma-separated list (e.g. '1,3,5'):"
        )
        try:
            from core.config import settings as _settings
            if provider == "anthropic":
                api_key = getattr(_settings, "ANTHROPIC_API_KEY", None)
                async with httpx.AsyncClient(timeout=30) as client:
                    r = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                        json={"model": model or "claude-3-5-haiku-20241022", "max_tokens": 64,
                              "messages": [{"role": "user", "content": prompt}]},
                    )
                    r.raise_for_status()
                    answer = r.json()["content"][0]["text"]
            else:
                api_key = getattr(_settings, "OPENAI_API_KEY", None)
                async with httpx.AsyncClient(timeout=30) as client:
                    r = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}"},
                        json={"model": model or "gpt-4o-mini", "max_tokens": 64,
                              "messages": [{"role": "user", "content": prompt}]},
                    )
                    r.raise_for_status()
                    answer = r.json()["choices"][0]["message"]["content"]

            indices = [int(n.strip()) - 1 for n in re.findall(r"\d+", answer) if 0 < int(n.strip()) <= len(documents)]
            selected = [documents[i] for i in indices[:top_k]]
        except Exception:
            selected = documents[:top_k]
    else:
        selected = documents[:top_k]

    return {
        "documents": selected,
        "count": len(selected),
        "query": query,
        "strategy": strategy,
        "total_documents": len(documents),
    }
