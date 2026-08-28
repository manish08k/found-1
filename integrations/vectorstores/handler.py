"""
Vector store nodes — additional vector database backends beyond pgvector.

Each store supports three operations: upsert, query, delete.

Nodes:
  vectorstore.pinecone.*       — Pinecone serverless (REST API)
  vectorstore.qdrant.*         — Qdrant (REST API)
  vectorstore.weaviate.*       — Weaviate (REST API v1)
  vectorstore.chroma.*         — Chroma (REST API / local)
  vectorstore.elasticsearch.*  — Elasticsearch kNN
  vectorstore.opensearch.*     — OpenSearch kNN
  vectorstore.redis.*          — Redis Stack vector search
  vectorstore.supabase.*       — Supabase pgvector via REST
  vectorstore.milvus.*         — Milvus / Zilliz REST API
  vectorstore.inmemory.*       — Pure in-process numpy cosine similarity
  vectorstore.faiss.*          — Faiss CPU index (in-process)
  vectorstore.upstash.*        — Upstash Vector REST API
  vectorstore.mongodb_atlas.*  — MongoDB Atlas Vector Search
"""
import json
import math
from collections import defaultdict
from typing import Any

import httpx
import structlog

from core.config import settings
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

# ─── shared: OpenAI embed helper ─────────────────────────────────────────────

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

    if provider == "cohere":
        api_key = settings.COHERE_API_KEY
        if not api_key:
            raise ValueError("COHERE_API_KEY required")
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                "https://api.cohere.ai/v1/embed",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"texts": [text], "model": model or "embed-english-v3.0",
                      "input_type": "search_query"},
            )
            r.raise_for_status()
            return r.json()["embeddings"][0]

    raise ValueError(f"Unsupported embed provider: {provider}")


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb + 1e-10)


# ─── In-memory vector store ──────────────────────────────────────────────────
_INMEMORY_STORE: dict[str, list[dict]] = defaultdict(list)


@register_node("vectorstore.inmemory.upsert")
async def vs_inmemory_upsert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Upsert documents into a named in-memory vector collection."""
    collection = config.get("collection", "default")
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")
    documents = input_data.get("documents", [])
    if not documents and "text" in input_data:
        documents = [{"content": input_data["text"], "metadata": {}}]

    upserted = 0
    for doc in documents:
        content = doc.get("content") or doc.get("text", "")
        meta = doc.get("metadata", {})
        doc_id = doc.get("id") or str(hash(content))
        vec = await _embed(content, embed_provider, embed_model)
        # Replace if ID exists
        _INMEMORY_STORE[collection] = [d for d in _INMEMORY_STORE[collection] if d["id"] != doc_id]
        _INMEMORY_STORE[collection].append({"id": doc_id, "content": content, "metadata": meta, "embedding": vec})
        upserted += 1
    return {"upserted": upserted, "collection": collection, "total": len(_INMEMORY_STORE[collection])}


@register_node("vectorstore.inmemory.query")
async def vs_inmemory_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Query the in-memory vector store by cosine similarity."""
    collection = config.get("collection", "default")
    top_k = int(config.get("top_k", 4))
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")
    query = input_data.get("query") or input_data.get("input", "")
    threshold = float(config.get("score_threshold", 0.0))

    docs = _INMEMORY_STORE[collection]
    if not docs:
        return {"documents": [], "count": 0, "query": query}

    q_vec = await _embed(query, embed_provider, embed_model)
    scored = [{"score": _cosine(q_vec, d["embedding"]), **{k: v for k, v in d.items() if k != "embedding"}}
              for d in docs]
    scored.sort(key=lambda x: x["score"], reverse=True)
    results = [d for d in scored if d["score"] >= threshold][:top_k]
    return {"documents": results, "count": len(results), "query": query}


@register_node("vectorstore.inmemory.delete")
async def vs_inmemory_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    collection = config.get("collection", "default")
    doc_ids = input_data.get("ids", [])
    if doc_ids:
        before = len(_INMEMORY_STORE[collection])
        _INMEMORY_STORE[collection] = [d for d in _INMEMORY_STORE[collection] if d["id"] not in doc_ids]
        deleted = before - len(_INMEMORY_STORE[collection])
    else:
        deleted = len(_INMEMORY_STORE[collection])
        _INMEMORY_STORE[collection].clear()
    return {"deleted": deleted, "collection": collection}


# ─── Faiss in-process vector store ───────────────────────────────────────────
_FAISS_STORE: dict[str, dict] = {}  # {collection: {ids, contents, metadatas, index}}


@register_node("vectorstore.faiss.upsert")
async def vs_faiss_upsert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Upsert documents into a Faiss flat IP index."""
    try:
        import faiss  # type: ignore
        import numpy as np
    except ImportError:
        raise ImportError("vectorstore.faiss requires faiss-cpu: pip install faiss-cpu numpy")

    collection = config.get("collection", "default")
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")
    documents = input_data.get("documents", [])
    if not documents and "text" in input_data:
        documents = [{"content": input_data["text"], "metadata": {}}]

    if collection not in _FAISS_STORE:
        _FAISS_STORE[collection] = {"ids": [], "contents": [], "metadatas": [], "index": None, "dim": 0}

    store = _FAISS_STORE[collection]

    for doc in documents:
        content = doc.get("content") or doc.get("text", "")
        meta = doc.get("metadata", {})
        doc_id = doc.get("id") or str(hash(content))
        vec = await _embed(content, embed_provider, embed_model)
        dim = len(vec)

        if store["index"] is None:
            store["index"] = faiss.IndexFlatIP(dim)
            store["dim"] = dim

        vec_np = np.array([vec], dtype=np.float32)
        faiss.normalize_L2(vec_np)
        store["index"].add(vec_np)
        store["ids"].append(doc_id)
        store["contents"].append(content)
        store["metadatas"].append(meta)

    return {"upserted": len(documents), "collection": collection, "total": len(store["ids"])}


@register_node("vectorstore.faiss.query")
async def vs_faiss_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Query a Faiss index by cosine similarity."""
    try:
        import faiss  # type: ignore
        import numpy as np
    except ImportError:
        raise ImportError("vectorstore.faiss requires faiss-cpu")

    collection = config.get("collection", "default")
    top_k = int(config.get("top_k", 4))
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")
    query = input_data.get("query") or input_data.get("input", "")

    store = _FAISS_STORE.get(collection)
    if not store or not store["ids"]:
        return {"documents": [], "count": 0, "query": query}

    vec = await _embed(query, embed_provider, embed_model)
    vec_np = np.array([vec], dtype=np.float32)
    faiss.normalize_L2(vec_np)
    scores, indices = store["index"].search(vec_np, min(top_k, len(store["ids"])))

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx >= 0:
            results.append({"id": store["ids"][idx], "content": store["contents"][idx],
                            "metadata": store["metadatas"][idx], "score": float(score)})
    return {"documents": results, "count": len(results), "query": query}


@register_node("vectorstore.faiss.delete")
async def vs_faiss_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    collection = config.get("collection", "default")
    if collection in _FAISS_STORE:
        del _FAISS_STORE[collection]
    return {"deleted": True, "collection": collection}


# ─── Pinecone ─────────────────────────────────────────────────────────────────

def _pinecone_headers(api_key: str) -> dict:
    return {"Api-Key": api_key, "Content-Type": "application/json"}


@register_node("vectorstore.pinecone.upsert")
async def vs_pinecone_upsert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    api_key = config.get("api_key") or getattr(settings, "PINECONE_API_KEY", "")
    index_host = config.get("index_host", "")  # e.g. https://my-index-xxxx.svc.us-east1-gcp.pinecone.io
    namespace = config.get("namespace", "")
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")

    if not api_key or not index_host:
        raise ValueError("vectorstore.pinecone requires api_key and index_host")

    documents = input_data.get("documents", [])
    if not documents and "text" in input_data:
        documents = [{"content": input_data["text"], "metadata": {}}]

    vectors = []
    for doc in documents:
        content = doc.get("content") or doc.get("text", "")
        meta = {**doc.get("metadata", {}), "text": content}
        doc_id = doc.get("id") or str(abs(hash(content)))
        vec = await _embed(content, embed_provider, embed_model)
        vectors.append({"id": doc_id, "values": vec, "metadata": meta})

    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{index_host}/vectors/upsert",
                         headers=_pinecone_headers(api_key),
                         json={"vectors": vectors, "namespace": namespace})
        r.raise_for_status()
    return {"upserted": len(vectors), "namespace": namespace}


@register_node("vectorstore.pinecone.query")
async def vs_pinecone_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    api_key = config.get("api_key") or getattr(settings, "PINECONE_API_KEY", "")
    index_host = config.get("index_host", "")
    namespace = config.get("namespace", "")
    top_k = int(config.get("top_k", 4))
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")
    query = input_data.get("query") or input_data.get("input", "")

    if not api_key or not index_host:
        raise ValueError("vectorstore.pinecone requires api_key and index_host")

    vec = await _embed(query, embed_provider, embed_model)
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{index_host}/query",
                         headers=_pinecone_headers(api_key),
                         json={"vector": vec, "topK": top_k,
                               "namespace": namespace, "includeMetadata": True})
        r.raise_for_status()
        matches = r.json().get("matches", [])

    docs = [{"id": m["id"], "score": m["score"],
             "content": m.get("metadata", {}).get("text", ""),
             "metadata": {k: v for k, v in m.get("metadata", {}).items() if k != "text"}}
            for m in matches]
    return {"documents": docs, "count": len(docs), "query": query}


@register_node("vectorstore.pinecone.delete")
async def vs_pinecone_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    api_key = config.get("api_key") or getattr(settings, "PINECONE_API_KEY", "")
    index_host = config.get("index_host", "")
    namespace = config.get("namespace", "")
    ids = input_data.get("ids", [])
    delete_all = config.get("delete_all", False)

    async with httpx.AsyncClient(timeout=15) as c:
        if delete_all:
            r = await c.post(f"{index_host}/vectors/delete",
                             headers=_pinecone_headers(api_key),
                             json={"deleteAll": True, "namespace": namespace})
        else:
            r = await c.post(f"{index_host}/vectors/delete",
                             headers=_pinecone_headers(api_key),
                             json={"ids": ids, "namespace": namespace})
        r.raise_for_status()
    return {"deleted": True, "ids": ids, "delete_all": delete_all}


# ─── Qdrant ───────────────────────────────────────────────────────────────────

@register_node("vectorstore.qdrant.upsert")
async def vs_qdrant_upsert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    qdrant_url = (config.get("url") or getattr(settings, "QDRANT_URL", "http://localhost:6333")).rstrip("/")
    api_key = config.get("api_key") or getattr(settings, "QDRANT_API_KEY", "")
    collection = config.get("collection", "default")
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")

    documents = input_data.get("documents", [])
    if not documents and "text" in input_data:
        documents = [{"content": input_data["text"], "metadata": {}}]

    headers: dict = {"Content-Type": "application/json"}
    if api_key:
        headers["api-key"] = api_key

    points = []
    for i, doc in enumerate(documents):
        content = doc.get("content") or doc.get("text", "")
        meta = {**doc.get("metadata", {}), "text": content}
        doc_id = doc.get("id") or str(abs(hash(content)) % (10**9))
        # Qdrant requires integer or UUID point IDs
        try:
            point_id = int(doc_id)
        except (ValueError, TypeError):
            import uuid as _uuid
            point_id = str(_uuid.uuid5(_uuid.NAMESPACE_DNS, str(doc_id)))
        vec = await _embed(content, embed_provider, embed_model)
        points.append({"id": point_id, "vector": vec, "payload": meta})

    async with httpx.AsyncClient(timeout=30) as c:
        # Ensure collection exists
        r = await c.get(f"{qdrant_url}/collections/{collection}", headers=headers)
        if r.status_code == 404 and points:
            dim = len(points[0]["vector"])
            await c.put(f"{qdrant_url}/collections/{collection}", headers=headers,
                        json={"vectors": {"size": dim, "distance": "Cosine"}})
        r = await c.put(f"{qdrant_url}/collections/{collection}/points",
                        headers=headers, json={"points": points})
        r.raise_for_status()
    return {"upserted": len(points), "collection": collection}


@register_node("vectorstore.qdrant.query")
async def vs_qdrant_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    qdrant_url = (config.get("url") or getattr(settings, "QDRANT_URL", "http://localhost:6333")).rstrip("/")
    api_key = config.get("api_key") or getattr(settings, "QDRANT_API_KEY", "")
    collection = config.get("collection", "default")
    top_k = int(config.get("top_k", 4))
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")
    query = input_data.get("query") or input_data.get("input", "")

    headers: dict = {"Content-Type": "application/json"}
    if api_key:
        headers["api-key"] = api_key

    vec = await _embed(query, embed_provider, embed_model)
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{qdrant_url}/collections/{collection}/points/search",
                         headers=headers,
                         json={"vector": vec, "limit": top_k, "with_payload": True})
        r.raise_for_status()
        results = r.json().get("result", [])

    docs = [{"id": str(r["id"]), "score": r["score"],
             "content": r.get("payload", {}).get("text", ""),
             "metadata": {k: v for k, v in r.get("payload", {}).items() if k != "text"}}
            for r in results]
    return {"documents": docs, "count": len(docs), "query": query}


@register_node("vectorstore.qdrant.delete")
async def vs_qdrant_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    qdrant_url = (config.get("url") or getattr(settings, "QDRANT_URL", "http://localhost:6333")).rstrip("/")
    api_key = config.get("api_key") or getattr(settings, "QDRANT_API_KEY", "")
    collection = config.get("collection", "default")
    ids = input_data.get("ids", [])
    delete_all = config.get("delete_all", False)

    headers: dict = {"Content-Type": "application/json"}
    if api_key:
        headers["api-key"] = api_key

    async with httpx.AsyncClient(timeout=15) as c:
        if delete_all:
            r = await c.delete(f"{qdrant_url}/collections/{collection}", headers=headers)
        else:
            r = await c.post(f"{qdrant_url}/collections/{collection}/points/delete",
                             headers=headers, json={"points": ids})
        r.raise_for_status()
    return {"deleted": True, "collection": collection}


# ─── Weaviate ─────────────────────────────────────────────────────────────────

@register_node("vectorstore.weaviate.upsert")
async def vs_weaviate_upsert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    weaviate_url = (config.get("url") or getattr(settings, "WEAVIATE_URL", "http://localhost:8080")).rstrip("/")
    api_key = config.get("api_key") or getattr(settings, "WEAVIATE_API_KEY", "")
    class_name = config.get("class_name", "Document")
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")

    documents = input_data.get("documents", [])
    if not documents and "text" in input_data:
        documents = [{"content": input_data["text"], "metadata": {}}]

    headers: dict = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # Ensure class exists
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{weaviate_url}/v1/schema/{class_name}", headers=headers)
        if r.status_code == 404:
            await c.post(f"{weaviate_url}/v1/schema", headers=headers,
                         json={"class": class_name, "vectorizer": "none",
                               "properties": [{"name": "text", "dataType": ["text"]},
                                              {"name": "metadata", "dataType": ["text"]}]})

        upserted = 0
        for doc in documents:
            content = doc.get("content") or doc.get("text", "")
            meta = doc.get("metadata", {})
            vec = await _embed(content, embed_provider, embed_model)
            obj = {"class": class_name, "properties": {"text": content, "metadata": json.dumps(meta)},
                   "vector": vec}
            r = await c.post(f"{weaviate_url}/v1/objects", headers=headers, json=obj)
            r.raise_for_status()
            upserted += 1

    return {"upserted": upserted, "class": class_name}


@register_node("vectorstore.weaviate.query")
async def vs_weaviate_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    weaviate_url = (config.get("url") or getattr(settings, "WEAVIATE_URL", "http://localhost:8080")).rstrip("/")
    api_key = config.get("api_key") or getattr(settings, "WEAVIATE_API_KEY", "")
    class_name = config.get("class_name", "Document")
    top_k = int(config.get("top_k", 4))
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")
    query = input_data.get("query") or input_data.get("input", "")

    headers: dict = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    vec = await _embed(query, embed_provider, embed_model)
    gql = f"""{{
      Get {{
        {class_name}(nearVector: {{vector: {json.dumps(vec)}, certainty: 0.5}}, limit: {top_k}) {{
          text metadata _additional {{ id certainty distance }}
        }}
      }}
    }}"""

    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{weaviate_url}/v1/graphql", headers=headers, json={"query": gql})
        r.raise_for_status()
        data = r.json()

    items = data.get("data", {}).get("Get", {}).get(class_name, [])
    docs = [{"id": item["_additional"]["id"],
             "content": item.get("text", ""),
             "metadata": json.loads(item.get("metadata", "{}") or "{}"),
             "score": item["_additional"].get("certainty", 0)}
            for item in items]
    return {"documents": docs, "count": len(docs), "query": query}


@register_node("vectorstore.weaviate.delete")
async def vs_weaviate_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    weaviate_url = (config.get("url") or getattr(settings, "WEAVIATE_URL", "http://localhost:8080")).rstrip("/")
    api_key = config.get("api_key") or getattr(settings, "WEAVIATE_API_KEY", "")
    class_name = config.get("class_name", "Document")
    ids = input_data.get("ids", [])

    headers: dict = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    deleted = 0
    async with httpx.AsyncClient(timeout=15) as c:
        if ids:
            for doc_id in ids:
                r = await c.delete(f"{weaviate_url}/v1/objects/{class_name}/{doc_id}", headers=headers)
                if r.status_code in (200, 204):
                    deleted += 1
        else:
            # Delete all objects in class
            r = await c.delete(f"{weaviate_url}/v1/schema/{class_name}", headers=headers)
            deleted = -1  # unknown count
    return {"deleted": deleted if deleted >= 0 else "all", "class": class_name}


# ─── Chroma ───────────────────────────────────────────────────────────────────

@register_node("vectorstore.chroma.upsert")
async def vs_chroma_upsert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    chroma_url = (config.get("url") or getattr(settings, "CHROMA_URL", "http://localhost:8000")).rstrip("/")
    collection_name = config.get("collection", "default")
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")

    documents = input_data.get("documents", [])
    if not documents and "text" in input_data:
        documents = [{"content": input_data["text"], "metadata": {}}]

    headers = {"Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=30) as c:
        # Get or create collection
        r = await c.post(f"{chroma_url}/api/v1/collections",
                         headers=headers,
                         json={"name": collection_name, "get_or_create": True})
        if r.status_code not in (200, 201):
            r = await c.get(f"{chroma_url}/api/v1/collections/{collection_name}", headers=headers)
        coll_id = r.json().get("id", collection_name)

        ids, embeddings, docs_list, metadatas = [], [], [], []
        for doc in documents:
            content = doc.get("content") or doc.get("text", "")
            meta = doc.get("metadata", {})
            doc_id = doc.get("id") or str(abs(hash(content)))
            vec = await _embed(content, embed_provider, embed_model)
            ids.append(doc_id)
            embeddings.append(vec)
            docs_list.append(content)
            metadatas.append(meta)

        r = await c.post(f"{chroma_url}/api/v1/collections/{coll_id}/upsert",
                         headers=headers,
                         json={"ids": ids, "embeddings": embeddings,
                               "documents": docs_list, "metadatas": metadatas})
        r.raise_for_status()
    return {"upserted": len(ids), "collection": collection_name}


@register_node("vectorstore.chroma.query")
async def vs_chroma_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    chroma_url = (config.get("url") or getattr(settings, "CHROMA_URL", "http://localhost:8000")).rstrip("/")
    collection_name = config.get("collection", "default")
    top_k = int(config.get("top_k", 4))
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")
    query = input_data.get("query") or input_data.get("input", "")

    headers = {"Content-Type": "application/json"}
    vec = await _embed(query, embed_provider, embed_model)

    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(f"{chroma_url}/api/v1/collections/{collection_name}", headers=headers)
        if r.status_code == 404:
            return {"documents": [], "count": 0, "query": query}
        coll_id = r.json().get("id", collection_name)
        r = await c.post(f"{chroma_url}/api/v1/collections/{coll_id}/query",
                         headers=headers,
                         json={"query_embeddings": [vec], "n_results": top_k,
                               "include": ["documents", "metadatas", "distances"]})
        r.raise_for_status()
        data = r.json()

    result_ids = data.get("ids", [[]])[0]
    result_docs = data.get("documents", [[]])[0]
    result_metas = data.get("metadatas", [[]])[0]
    result_dists = data.get("distances", [[]])[0]

    docs = [{"id": rid, "content": rdoc, "metadata": rmeta or {},
             "score": 1 - rdist}
            for rid, rdoc, rmeta, rdist in zip(result_ids, result_docs, result_metas, result_dists)]
    return {"documents": docs, "count": len(docs), "query": query}


@register_node("vectorstore.chroma.delete")
async def vs_chroma_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    chroma_url = (config.get("url") or getattr(settings, "CHROMA_URL", "http://localhost:8000")).rstrip("/")
    collection_name = config.get("collection", "default")
    ids = input_data.get("ids", [])
    headers = {"Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{chroma_url}/api/v1/collections/{collection_name}", headers=headers)
        if r.status_code == 404:
            return {"deleted": 0}
        coll_id = r.json().get("id", collection_name)
        if ids:
            r = await c.post(f"{chroma_url}/api/v1/collections/{coll_id}/delete",
                             headers=headers, json={"ids": ids})
        else:
            r = await c.delete(f"{chroma_url}/api/v1/collections/{collection_name}", headers=headers)
        r.raise_for_status()
    return {"deleted": len(ids) if ids else "all", "collection": collection_name}


# ─── Elasticsearch ────────────────────────────────────────────────────────────

@register_node("vectorstore.elasticsearch.upsert")
async def vs_elasticsearch_upsert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    es_url = (config.get("url") or getattr(settings, "ELASTICSEARCH_URL", "http://localhost:9200")).rstrip("/")
    api_key = config.get("api_key") or getattr(settings, "ELASTICSEARCH_API_KEY", "")
    index_name = config.get("index", "autoflow_docs")
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")

    documents = input_data.get("documents", [])
    if not documents and "text" in input_data:
        documents = [{"content": input_data["text"], "metadata": {}}]

    headers: dict = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"ApiKey {api_key}"

    async with httpx.AsyncClient(timeout=30) as c:
        # Create index if not exists
        r = await c.head(f"{es_url}/{index_name}", headers=headers)
        if r.status_code == 404:
            dim = 1536  # default
            if documents:
                sample_vec = await _embed((documents[0].get("content") or "test"), embed_provider, embed_model)
                dim = len(sample_vec)
            await c.put(f"{es_url}/{index_name}", headers=headers,
                        json={"mappings": {"properties": {
                            "content": {"type": "text"},
                            "metadata": {"type": "object"},
                            "embedding": {"type": "dense_vector", "dims": dim, "index": True, "similarity": "cosine"}
                        }}})

        upserted = 0
        for doc in documents:
            content = doc.get("content") or doc.get("text", "")
            meta = doc.get("metadata", {})
            doc_id = doc.get("id") or str(abs(hash(content)))
            vec = await _embed(content, embed_provider, embed_model)
            r = await c.put(f"{es_url}/{index_name}/_doc/{doc_id}", headers=headers,
                            json={"content": content, "metadata": meta, "embedding": vec})
            r.raise_for_status()
            upserted += 1

    return {"upserted": upserted, "index": index_name}


@register_node("vectorstore.elasticsearch.query")
async def vs_elasticsearch_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    es_url = (config.get("url") or getattr(settings, "ELASTICSEARCH_URL", "http://localhost:9200")).rstrip("/")
    api_key = config.get("api_key") or getattr(settings, "ELASTICSEARCH_API_KEY", "")
    index_name = config.get("index", "autoflow_docs")
    top_k = int(config.get("top_k", 4))
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")
    query = input_data.get("query") or input_data.get("input", "")

    headers: dict = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"ApiKey {api_key}"

    vec = await _embed(query, embed_provider, embed_model)
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{es_url}/{index_name}/_search", headers=headers,
                         json={"knn": {"field": "embedding", "query_vector": vec,
                                       "k": top_k, "num_candidates": top_k * 10},
                               "_source": ["content", "metadata"], "size": top_k})
        r.raise_for_status()
        hits = r.json().get("hits", {}).get("hits", [])

    docs = [{"id": h["_id"], "content": h["_source"].get("content", ""),
             "metadata": h["_source"].get("metadata", {}), "score": h.get("_score", 0)}
            for h in hits]
    return {"documents": docs, "count": len(docs), "query": query}


@register_node("vectorstore.elasticsearch.delete")
async def vs_elasticsearch_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    es_url = (config.get("url") or getattr(settings, "ELASTICSEARCH_URL", "http://localhost:9200")).rstrip("/")
    api_key = config.get("api_key") or getattr(settings, "ELASTICSEARCH_API_KEY", "")
    index_name = config.get("index", "autoflow_docs")
    ids = input_data.get("ids", [])
    headers: dict = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"ApiKey {api_key}"

    async with httpx.AsyncClient(timeout=15) as c:
        if ids:
            bulk = "\n".join(f'{{"delete":{{"_index":"{index_name}","_id":"{i}"}}}}\n' for i in ids)
            r = await c.post(f"{es_url}/_bulk", headers={**headers, "Content-Type": "application/x-ndjson"},
                             content=bulk + "\n")
        else:
            r = await c.delete(f"{es_url}/{index_name}", headers=headers)
        r.raise_for_status()
    return {"deleted": len(ids) if ids else "all", "index": index_name}


# ─── Supabase vector ──────────────────────────────────────────────────────────

@register_node("vectorstore.supabase.upsert")
async def vs_supabase_upsert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    supabase_url = (config.get("url") or getattr(settings, "SUPABASE_URL", "")).rstrip("/")
    service_key = config.get("service_key") or getattr(settings, "SUPABASE_SERVICE_KEY", "")
    table = config.get("table", "documents")
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")

    if not supabase_url or not service_key:
        raise ValueError("vectorstore.supabase requires url and service_key")

    documents = input_data.get("documents", [])
    if not documents and "text" in input_data:
        documents = [{"content": input_data["text"], "metadata": {}}]

    headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}",
               "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}

    records = []
    for doc in documents:
        content = doc.get("content") or doc.get("text", "")
        meta = doc.get("metadata", {})
        doc_id = doc.get("id") or str(abs(hash(content)))
        vec = await _embed(content, embed_provider, embed_model)
        records.append({"id": doc_id, "content": content, "metadata": meta, "embedding": vec})

    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{supabase_url}/rest/v1/{table}", headers=headers, json=records)
        r.raise_for_status()
    return {"upserted": len(records), "table": table}


@register_node("vectorstore.supabase.query")
async def vs_supabase_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    supabase_url = (config.get("url") or getattr(settings, "SUPABASE_URL", "")).rstrip("/")
    service_key = config.get("service_key") or getattr(settings, "SUPABASE_SERVICE_KEY", "")
    function_name = config.get("function", "match_documents")
    top_k = int(config.get("top_k", 4))
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")
    query = input_data.get("query") or input_data.get("input", "")

    if not supabase_url or not service_key:
        raise ValueError("vectorstore.supabase requires url and service_key")

    headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}",
               "Content-Type": "application/json"}

    vec = await _embed(query, embed_provider, embed_model)
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{supabase_url}/rest/v1/rpc/{function_name}", headers=headers,
                         json={"query_embedding": vec, "match_count": top_k})
        r.raise_for_status()
        results = r.json()

    docs = [{"id": r.get("id"), "content": r.get("content", ""),
             "metadata": r.get("metadata", {}), "score": r.get("similarity", 0)}
            for r in results]
    return {"documents": docs, "count": len(docs), "query": query}


@register_node("vectorstore.supabase.delete")
async def vs_supabase_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    supabase_url = (config.get("url") or getattr(settings, "SUPABASE_URL", "")).rstrip("/")
    service_key = config.get("service_key") or getattr(settings, "SUPABASE_SERVICE_KEY", "")
    table = config.get("table", "documents")
    ids = input_data.get("ids", [])

    headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}",
               "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=15) as c:
        if ids:
            ids_str = ",".join(f'"{i}"' for i in ids)
            r = await c.delete(f"{supabase_url}/rest/v1/{table}?id=in.({ids_str})", headers=headers)
        else:
            r = await c.delete(f"{supabase_url}/rest/v1/{table}?id=neq.null", headers=headers)
        r.raise_for_status()
    return {"deleted": len(ids) if ids else "all", "table": table}


# ─── Upstash Vector ───────────────────────────────────────────────────────────

@register_node("vectorstore.upstash.upsert")
async def vs_upstash_upsert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    upstash_url = (config.get("url") or getattr(settings, "UPSTASH_VECTOR_REST_URL", "")).rstrip("/")
    upstash_token = config.get("token") or getattr(settings, "UPSTASH_VECTOR_REST_TOKEN", "")
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")

    if not upstash_url or not upstash_token:
        raise ValueError("vectorstore.upstash requires url and token")

    documents = input_data.get("documents", [])
    if not documents and "text" in input_data:
        documents = [{"content": input_data["text"], "metadata": {}}]

    headers = {"Authorization": f"Bearer {upstash_token}", "Content-Type": "application/json"}
    vectors = []
    for doc in documents:
        content = doc.get("content") or doc.get("text", "")
        meta = {**doc.get("metadata", {}), "text": content}
        doc_id = doc.get("id") or str(abs(hash(content)))
        vec = await _embed(content, embed_provider, embed_model)
        vectors.append({"id": doc_id, "vector": vec, "metadata": meta})

    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{upstash_url}/upsert", headers=headers, json=vectors)
        r.raise_for_status()
    return {"upserted": len(vectors)}


@register_node("vectorstore.upstash.query")
async def vs_upstash_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    upstash_url = (config.get("url") or getattr(settings, "UPSTASH_VECTOR_REST_URL", "")).rstrip("/")
    upstash_token = config.get("token") or getattr(settings, "UPSTASH_VECTOR_REST_TOKEN", "")
    top_k = int(config.get("top_k", 4))
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")
    query = input_data.get("query") or input_data.get("input", "")

    headers = {"Authorization": f"Bearer {upstash_token}", "Content-Type": "application/json"}
    vec = await _embed(query, embed_provider, embed_model)

    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{upstash_url}/query", headers=headers,
                         json={"vector": vec, "topK": top_k, "includeMetadata": True})
        r.raise_for_status()
        results = r.json().get("result", [])

    docs = [{"id": r["id"], "score": r["score"],
             "content": r.get("metadata", {}).get("text", ""),
             "metadata": {k: v for k, v in r.get("metadata", {}).items() if k != "text"}}
            for r in results]
    return {"documents": docs, "count": len(docs), "query": query}


@register_node("vectorstore.upstash.delete")
async def vs_upstash_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    upstash_url = (config.get("url") or getattr(settings, "UPSTASH_VECTOR_REST_URL", "")).rstrip("/")
    upstash_token = config.get("token") or getattr(settings, "UPSTASH_VECTOR_REST_TOKEN", "")
    ids = input_data.get("ids", [])
    headers = {"Authorization": f"Bearer {upstash_token}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=15) as c:
        if ids:
            r = await c.delete(f"{upstash_url}/delete", headers=headers, json=ids)
        else:
            r = await c.delete(f"{upstash_url}/reset", headers=headers)
        r.raise_for_status()
    return {"deleted": len(ids) if ids else "all"}


# ─── MongoDB Atlas Vector Search ──────────────────────────────────────────────

@register_node("vectorstore.mongodb_atlas.upsert")
async def vs_mongodb_atlas_upsert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    mongo_url = config.get("url") or getattr(settings, "MONGODB_URL", "mongodb://localhost:27017")
    database = config.get("database", "autoflow")
    collection_name = config.get("collection", "documents")
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")

    try:
        from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore
    except ImportError:
        raise ImportError("vectorstore.mongodb_atlas requires motor: pip install motor")

    documents = input_data.get("documents", [])
    if not documents and "text" in input_data:
        documents = [{"content": input_data["text"], "metadata": {}}]

    client = AsyncIOMotorClient(mongo_url)
    coll = client[database][collection_name]
    try:
        upserted = 0
        for doc in documents:
            content = doc.get("content") or doc.get("text", "")
            meta = doc.get("metadata", {})
            doc_id = doc.get("id") or str(abs(hash(content)))
            vec = await _embed(content, embed_provider, embed_model)
            await coll.update_one({"_id": doc_id},
                                  {"$set": {"content": content, "metadata": meta, "embedding": vec}},
                                  upsert=True)
            upserted += 1
    finally:
        client.close()

    return {"upserted": upserted, "collection": collection_name}


@register_node("vectorstore.mongodb_atlas.query")
async def vs_mongodb_atlas_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    mongo_url = config.get("url") or getattr(settings, "MONGODB_URL", "mongodb://localhost:27017")
    database = config.get("database", "autoflow")
    collection_name = config.get("collection", "documents")
    index_name = config.get("index_name", "vector_index")
    top_k = int(config.get("top_k", 4))
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")
    query = input_data.get("query") or input_data.get("input", "")

    try:
        from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore
    except ImportError:
        raise ImportError("vectorstore.mongodb_atlas requires motor")

    vec = await _embed(query, embed_provider, embed_model)
    client = AsyncIOMotorClient(mongo_url)
    coll = client[database][collection_name]
    try:
        pipeline = [{"$vectorSearch": {"index": index_name, "path": "embedding",
                                       "queryVector": vec, "numCandidates": top_k * 10,
                                       "limit": top_k}},
                    {"$project": {"_id": 1, "content": 1, "metadata": 1,
                                  "score": {"$meta": "vectorSearchScore"}}}]
        cursor = coll.aggregate(pipeline)
        results = await cursor.to_list(length=top_k)
    finally:
        client.close()

    docs = [{"id": str(r["_id"]), "content": r.get("content", ""),
             "metadata": r.get("metadata", {}), "score": r.get("score", 0)}
            for r in results]
    return {"documents": docs, "count": len(docs), "query": query}


@register_node("vectorstore.mongodb_atlas.delete")
async def vs_mongodb_atlas_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    mongo_url = config.get("url") or getattr(settings, "MONGODB_URL", "mongodb://localhost:27017")
    database = config.get("database", "autoflow")
    collection_name = config.get("collection", "documents")
    ids = input_data.get("ids", [])

    try:
        from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore
    except ImportError:
        raise ImportError("vectorstore.mongodb_atlas requires motor")

    client = AsyncIOMotorClient(mongo_url)
    coll = client[database][collection_name]
    try:
        if ids:
            result = await coll.delete_many({"_id": {"$in": ids}})
            deleted = result.deleted_count
        else:
            result = await coll.delete_many({})
            deleted = result.deleted_count
    finally:
        client.close()

    return {"deleted": deleted, "collection": collection_name}


# ─── Milvus / Zilliz ─────────────────────────────────────────────────────────

@register_node("vectorstore.milvus.upsert")
async def vs_milvus_upsert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    milvus_url = (config.get("url") or getattr(settings, "MILVUS_URL", "http://localhost:19530")).rstrip("/")
    token = config.get("token") or getattr(settings, "MILVUS_TOKEN", "")
    collection_name = config.get("collection", "autoflow_docs")
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")

    documents = input_data.get("documents", [])
    if not documents and "text" in input_data:
        documents = [{"content": input_data["text"], "metadata": {}}]

    headers: dict = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Use Milvus REST API v2
    rows = []
    for doc in documents:
        content = doc.get("content") or doc.get("text", "")
        meta = doc.get("metadata", {})
        doc_id = doc.get("id") or str(abs(hash(content)) % (2**31))
        vec = await _embed(content, embed_provider, embed_model)
        rows.append({"id": int(doc_id) if str(doc_id).isdigit() else abs(hash(doc_id)) % (2**31),
                     "content": content, "metadata": json.dumps(meta), "embedding": vec})

    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{milvus_url}/v2/vectordb/entities/upsert", headers=headers,
                         json={"collectionName": collection_name, "data": rows})
        r.raise_for_status()
    return {"upserted": len(rows), "collection": collection_name}


@register_node("vectorstore.milvus.query")
async def vs_milvus_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    milvus_url = (config.get("url") or getattr(settings, "MILVUS_URL", "http://localhost:19530")).rstrip("/")
    token = config.get("token") or getattr(settings, "MILVUS_TOKEN", "")
    collection_name = config.get("collection", "autoflow_docs")
    top_k = int(config.get("top_k", 4))
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")
    query = input_data.get("query") or input_data.get("input", "")

    headers: dict = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    vec = await _embed(query, embed_provider, embed_model)
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{milvus_url}/v2/vectordb/entities/search", headers=headers,
                         json={"collectionName": collection_name, "data": [vec], "limit": top_k,
                               "outputFields": ["content", "metadata"]})
        r.raise_for_status()
        results = r.json().get("data", [])

    docs = [{"id": str(r.get("id", "")), "score": r.get("distance", 0),
             "content": r.get("content", ""),
             "metadata": json.loads(r.get("metadata", "{}") or "{}")}
            for r in results]
    return {"documents": docs, "count": len(docs), "query": query}


@register_node("vectorstore.milvus.delete")
async def vs_milvus_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    milvus_url = (config.get("url") or getattr(settings, "MILVUS_URL", "http://localhost:19530")).rstrip("/")
    token = config.get("token") or getattr(settings, "MILVUS_TOKEN", "")
    collection_name = config.get("collection", "autoflow_docs")
    ids = input_data.get("ids", [])

    headers: dict = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=15) as c:
        if ids:
            r = await c.post(f"{milvus_url}/v2/vectordb/entities/delete", headers=headers,
                             json={"collectionName": collection_name,
                                   "filter": f"id in [{','.join(str(i) for i in ids)}]"})
        else:
            r = await c.post(f"{milvus_url}/v2/vectordb/collections/drop", headers=headers,
                             json={"collectionName": collection_name})
        r.raise_for_status()
    return {"deleted": len(ids) if ids else "all", "collection": collection_name}


# ─── OpenSearch ───────────────────────────────────────────────────────────────

@register_node("vectorstore.opensearch.upsert")
async def vs_opensearch_upsert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    os_url = (config.get("url") or getattr(settings, "OPENSEARCH_URL", "http://localhost:9200")).rstrip("/")
    username = config.get("username", "admin")
    password = config.get("password") or getattr(settings, "OPENSEARCH_PASSWORD", "admin")
    index_name = config.get("index", "autoflow_docs")
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")

    documents = input_data.get("documents", [])
    if not documents and "text" in input_data:
        documents = [{"content": input_data["text"], "metadata": {}}]

    auth = (username, password)
    headers = {"Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=30, auth=auth) as c:
        r = await c.head(f"{os_url}/{index_name}", headers=headers)
        if r.status_code == 404 and documents:
            sample = await _embed(documents[0].get("content", "test"), embed_provider, embed_model)
            await c.put(f"{os_url}/{index_name}", headers=headers,
                        json={"mappings": {"properties": {
                            "content": {"type": "text"},
                            "metadata": {"type": "object"},
                            "embedding": {"type": "knn_vector", "dimension": len(sample)}
                        }}, "settings": {"index.knn": True}})

        upserted = 0
        for doc in documents:
            content = doc.get("content") or doc.get("text", "")
            meta = doc.get("metadata", {})
            doc_id = doc.get("id") or str(abs(hash(content)))
            vec = await _embed(content, embed_provider, embed_model)
            r = await c.put(f"{os_url}/{index_name}/_doc/{doc_id}", headers=headers,
                            json={"content": content, "metadata": meta, "embedding": vec})
            r.raise_for_status()
            upserted += 1

    return {"upserted": upserted, "index": index_name}


@register_node("vectorstore.opensearch.query")
async def vs_opensearch_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    os_url = (config.get("url") or getattr(settings, "OPENSEARCH_URL", "http://localhost:9200")).rstrip("/")
    username = config.get("username", "admin")
    password = config.get("password") or getattr(settings, "OPENSEARCH_PASSWORD", "admin")
    index_name = config.get("index", "autoflow_docs")
    top_k = int(config.get("top_k", 4))
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")
    query = input_data.get("query") or input_data.get("input", "")

    vec = await _embed(query, embed_provider, embed_model)
    auth = (username, password)

    async with httpx.AsyncClient(timeout=20, auth=auth) as c:
        r = await c.post(f"{os_url}/{index_name}/_search",
                         headers={"Content-Type": "application/json"},
                         json={"query": {"knn": {"embedding": {"vector": vec, "k": top_k}}}, "size": top_k})
        r.raise_for_status()
        hits = r.json().get("hits", {}).get("hits", [])

    docs = [{"id": h["_id"], "content": h["_source"].get("content", ""),
             "metadata": h["_source"].get("metadata", {}), "score": h.get("_score", 0)}
            for h in hits]
    return {"documents": docs, "count": len(docs), "query": query}


@register_node("vectorstore.opensearch.delete")
async def vs_opensearch_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    os_url = (config.get("url") or getattr(settings, "OPENSEARCH_URL", "http://localhost:9200")).rstrip("/")
    username = config.get("username", "admin")
    password = config.get("password") or getattr(settings, "OPENSEARCH_PASSWORD", "admin")
    index_name = config.get("index", "autoflow_docs")
    ids = input_data.get("ids", [])
    auth = (username, password)

    async with httpx.AsyncClient(timeout=15, auth=auth) as c:
        if ids:
            bulk = "\n".join(f'{{"delete":{{"_index":"{index_name}","_id":"{i}"}}}}\n' for i in ids)
            r = await c.post(f"{os_url}/_bulk",
                             headers={"Content-Type": "application/x-ndjson"},
                             content=bulk + "\n")
        else:
            r = await c.delete(f"{os_url}/{index_name}")
        r.raise_for_status()
    return {"deleted": len(ids) if ids else "all", "index": index_name}
