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


# ─── Astra DB (DataStax) ─────────────────────────────────────────────────────

@register_node("vectorstore.astra.upsert")
async def vs_astra_upsert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    token = getattr(settings, "ASTRA_DB_APPLICATION_TOKEN", None)
    endpoint = config.get("endpoint") or getattr(settings, "ASTRA_DB_ENDPOINT", None)
    if not token or not endpoint:
        raise ValueError("vectorstore.astra requires ASTRA_DB_APPLICATION_TOKEN and ASTRA_DB_ENDPOINT")
    keyspace = config.get("keyspace", "default_keyspace")
    collection = config.get("collection", "documents")
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")
    documents = input_data.get("documents", [])
    upserted = 0
    async with httpx.AsyncClient(timeout=60) as client:
        for doc in documents:
            content = doc.get("content") or doc.get("text", "")
            meta = doc.get("metadata", {})
            doc_id = doc.get("id") or str(hash(content))
            vec = await _embed(content, embed_provider, embed_model)
            r = await client.post(
                f"{endpoint}/api/json/v1/{keyspace}/{collection}",
                headers={"Token": token, "Content-Type": "application/json"},
                json={"insertOne": {"document": {"_id": doc_id, "content": content, "$vector": vec, **meta}}},
            )
            r.raise_for_status()
            upserted += 1
    return {"upserted": upserted, "collection": collection}

@register_node("vectorstore.astra.query")
async def vs_astra_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    token = getattr(settings, "ASTRA_DB_APPLICATION_TOKEN", None)
    endpoint = config.get("endpoint") or getattr(settings, "ASTRA_DB_ENDPOINT", None)
    if not token or not endpoint:
        raise ValueError("vectorstore.astra requires ASTRA_DB_APPLICATION_TOKEN and ASTRA_DB_ENDPOINT")
    keyspace = config.get("keyspace", "default_keyspace")
    collection = config.get("collection", "documents")
    query = config.get("query") or input_data.get("query", "")
    top_k = int(config.get("top_k", 4))
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")
    vec = await _embed(query, embed_provider, embed_model)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{endpoint}/api/json/v1/{keyspace}/{collection}",
            headers={"Token": token},
            json={"find": {"sort": {"$vector": vec}, "options": {"limit": top_k, "includeSimilarity": True}}},
        )
        r.raise_for_status()
        data = r.json()
    docs = data.get("data", {}).get("documents", [])
    results = [{"id": d.get("_id"), "content": d.get("content", ""), "score": d.get("$similarity"), "metadata": {k: v for k, v in d.items() if not k.startswith("$") and k not in ("_id", "content")}} for d in docs]
    return {"results": results, "query": query, "collection": collection}

@register_node("vectorstore.astra.delete")
async def vs_astra_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    token = getattr(settings, "ASTRA_DB_APPLICATION_TOKEN", None)
    endpoint = config.get("endpoint") or getattr(settings, "ASTRA_DB_ENDPOINT", None)
    if not token or not endpoint:
        raise ValueError("vectorstore.astra requires ASTRA_DB_APPLICATION_TOKEN and ASTRA_DB_ENDPOINT")
    keyspace = config.get("keyspace", "default_keyspace")
    collection = config.get("collection", "documents")
    ids = config.get("ids") or input_data.get("ids") or []
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{endpoint}/api/json/v1/{keyspace}/{collection}",
            headers={"Token": token},
            json={"deleteMany": {"filter": {"_id": {"$in": ids}}}},
        )
        r.raise_for_status()
    return {"deleted": len(ids), "collection": collection}


# ─── Meilisearch ──────────────────────────────────────────────────────────────

@register_node("vectorstore.meilisearch.upsert")
async def vs_meilisearch_upsert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    url = config.get("url") or getattr(settings, "MEILISEARCH_URL", "http://localhost:7700")
    api_key = config.get("api_key") or getattr(settings, "MEILISEARCH_API_KEY", "")
    index = config.get("index_name", "documents")
    documents = input_data.get("documents", [])
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    docs_to_add = []
    for doc in documents:
        content = doc.get("content") or doc.get("text", "")
        meta = doc.get("metadata", {})
        doc_id = doc.get("id") or str(abs(hash(content)))
        docs_to_add.append({"id": doc_id, "content": content, **meta})
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{url}/indexes/{index}/documents", headers=headers, json=docs_to_add)
        r.raise_for_status()
    return {"upserted": len(docs_to_add), "index": index}

@register_node("vectorstore.meilisearch.query")
async def vs_meilisearch_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    url = config.get("url") or getattr(settings, "MEILISEARCH_URL", "http://localhost:7700")
    api_key = config.get("api_key") or getattr(settings, "MEILISEARCH_API_KEY", "")
    index = config.get("index_name", "documents")
    query = config.get("query") or input_data.get("query", "")
    top_k = int(config.get("top_k", 4))
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{url}/indexes/{index}/search", headers=headers, json={"q": query, "limit": top_k})
        r.raise_for_status()
        data = r.json()
    hits = data.get("hits", [])
    results = [{"id": h.get("id"), "content": h.get("content", ""), "score": h.get("_rankingScore"), "metadata": {k: v for k, v in h.items() if k not in ("id", "content", "_rankingScore")}} for h in hits]
    return {"results": results, "query": query, "index": index}

@register_node("vectorstore.meilisearch.delete")
async def vs_meilisearch_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    url = config.get("url") or getattr(settings, "MEILISEARCH_URL", "http://localhost:7700")
    api_key = config.get("api_key") or getattr(settings, "MEILISEARCH_API_KEY", "")
    index = config.get("index_name", "documents")
    doc_id = config.get("id") or input_data.get("id")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    async with httpx.AsyncClient(timeout=30) as client:
        if doc_id:
            r = await client.delete(f"{url}/indexes/{index}/documents/{doc_id}", headers=headers)
        else:
            r = await client.delete(f"{url}/indexes/{index}/documents", headers=headers)
        r.raise_for_status()
    return {"deleted": True, "index": index}


# ─── Vectara ─────────────────────────────────────────────────────────────────

@register_node("vectorstore.vectara.upsert")
async def vs_vectara_upsert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    api_key = config.get("api_key") or getattr(settings, "VECTARA_API_KEY", None)
    corpus_id = config.get("corpus_id") or getattr(settings, "VECTARA_CORPUS_ID", None)
    if not api_key or not corpus_id:
        raise ValueError("vectorstore.vectara requires VECTARA_API_KEY and VECTARA_CORPUS_ID")
    documents = input_data.get("documents", [])
    upserted = 0
    async with httpx.AsyncClient(timeout=60) as client:
        for doc in documents:
            content = doc.get("content") or doc.get("text", "")
            meta = doc.get("metadata", {})
            doc_id = doc.get("id") or str(abs(hash(content)))
            r = await client.post(
                f"https://api.vectara.io/v2/corpora/{corpus_id}/documents",
                headers={"x-api-key": api_key, "Content-Type": "application/json"},
                json={"id": doc_id, "type": "core", "document_parts": [{"text": content, "metadata": meta}]},
            )
            if r.is_success:
                upserted += 1
    return {"upserted": upserted, "corpus_id": corpus_id}

@register_node("vectorstore.vectara.query")
async def vs_vectara_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    api_key = config.get("api_key") or getattr(settings, "VECTARA_API_KEY", None)
    corpus_id = config.get("corpus_id") or getattr(settings, "VECTARA_CORPUS_ID", None)
    if not api_key or not corpus_id:
        raise ValueError("vectorstore.vectara requires VECTARA_API_KEY and VECTARA_CORPUS_ID")
    query = config.get("query") or input_data.get("query", "")
    top_k = int(config.get("top_k", 4))
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            "https://api.vectara.io/v2/query",
            headers={"x-api-key": api_key},
            json={"query": query, "search": {"corpora": [{"corpus_id": corpus_id}], "limit": top_k}},
        )
        r.raise_for_status()
        data = r.json()
    items = data.get("search_results", [])
    results = [{"id": it.get("document_id"), "content": it.get("text", ""), "score": it.get("score"), "metadata": it.get("part_metadata", {})} for it in items]
    return {"results": results, "query": query, "corpus_id": corpus_id}

@register_node("vectorstore.vectara.delete")
async def vs_vectara_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    api_key = config.get("api_key") or getattr(settings, "VECTARA_API_KEY", None)
    corpus_id = config.get("corpus_id") or getattr(settings, "VECTARA_CORPUS_ID", None)
    if not api_key or not corpus_id:
        raise ValueError("vectorstore.vectara requires VECTARA_API_KEY and VECTARA_CORPUS_ID")
    doc_id = config.get("id") or input_data.get("id")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.delete(
            f"https://api.vectara.io/v2/corpora/{corpus_id}/documents/{doc_id}",
            headers={"x-api-key": api_key},
        )
        r.raise_for_status()
    return {"deleted": True, "corpus_id": corpus_id, "document_id": doc_id}


# ─── Zep Vector Store ─────────────────────────────────────────────────────────

@register_node("vectorstore.zep.upsert")
async def vs_zep_upsert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    zep_url = config.get("url") or getattr(settings, "ZEP_URL", "http://localhost:8000")
    api_key = config.get("api_key") or getattr(settings, "ZEP_API_KEY", "")
    collection = config.get("collection", "default")
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")
    documents = input_data.get("documents", [])
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    docs_payload = []
    for doc in documents:
        content = doc.get("content") or doc.get("text", "")
        meta = doc.get("metadata", {})
        doc_id = doc.get("id") or str(abs(hash(content)))
        vec = await _embed(content, embed_provider, embed_model)
        docs_payload.append({"uuid": doc_id, "content": content, "metadata": meta, "embedding": vec})
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{zep_url}/api/v1/collection/{collection}/documents", headers=headers, json=docs_payload)
        r.raise_for_status()
    return {"upserted": len(docs_payload), "collection": collection}

@register_node("vectorstore.zep.query")
async def vs_zep_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    zep_url = config.get("url") or getattr(settings, "ZEP_URL", "http://localhost:8000")
    api_key = config.get("api_key") or getattr(settings, "ZEP_API_KEY", "")
    collection = config.get("collection", "default")
    query = config.get("query") or input_data.get("query", "")
    top_k = int(config.get("top_k", 4))
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{zep_url}/api/v1/collection/{collection}/search", headers=headers, json={"text": query, "limit": top_k})
        r.raise_for_status()
        data = r.json()
    results = [{"id": d.get("uuid"), "content": d.get("content", ""), "score": d.get("dist"), "metadata": d.get("metadata", {})} for d in (data.get("results") or [])]
    return {"results": results, "query": query, "collection": collection}

@register_node("vectorstore.zep.delete")
async def vs_zep_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    zep_url = config.get("url") or getattr(settings, "ZEP_URL", "http://localhost:8000")
    api_key = config.get("api_key") or getattr(settings, "ZEP_API_KEY", "")
    collection = config.get("collection", "default")
    doc_id = config.get("id") or input_data.get("id")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.delete(f"{zep_url}/api/v1/collection/{collection}/documents/{doc_id}", headers=headers)
        r.raise_for_status()
    return {"deleted": True, "collection": collection}


# ─── Zep Cloud Vector Store ───────────────────────────────────────────────────

@register_node("vectorstore.zep_cloud.upsert")
async def vs_zep_cloud_upsert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    api_key = config.get("api_key") or getattr(settings, "ZEP_CLOUD_API_KEY", None)
    if not api_key:
        raise ValueError("vectorstore.zep_cloud requires ZEP_CLOUD_API_KEY")
    return await vs_zep_upsert({**config, "url": "https://api.getzep.com", "api_key": api_key}, input_data, credential_id, db)

@register_node("vectorstore.zep_cloud.query")
async def vs_zep_cloud_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    api_key = config.get("api_key") or getattr(settings, "ZEP_CLOUD_API_KEY", None)
    if not api_key:
        raise ValueError("vectorstore.zep_cloud requires ZEP_CLOUD_API_KEY")
    return await vs_zep_query({**config, "url": "https://api.getzep.com", "api_key": api_key}, input_data, credential_id, db)

@register_node("vectorstore.zep_cloud.delete")
async def vs_zep_cloud_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    api_key = config.get("api_key") or getattr(settings, "ZEP_CLOUD_API_KEY", None)
    if not api_key:
        raise ValueError("vectorstore.zep_cloud requires ZEP_CLOUD_API_KEY")
    return await vs_zep_delete({**config, "url": "https://api.getzep.com", "api_key": api_key}, input_data, credential_id, db)


# ─── Postgres pgvector ────────────────────────────────────────────────────────

@register_node("vectorstore.postgres.upsert")
async def vs_postgres_upsert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Upsert into PostgreSQL using pgvector extension."""
    conn_str = config.get("connection_string") or getattr(settings, "DATABASE_URL", "")
    table = config.get("table_name", "vector_documents")
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")
    documents = input_data.get("documents", [])
    # Use asyncpg if available, otherwise psycopg2
    try:
        import asyncpg
        # Convert asyncpg DSN
        dsn = conn_str.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://")
        conn = await asyncpg.connect(dsn)
        try:
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    id TEXT PRIMARY KEY,
                    content TEXT,
                    metadata JSONB,
                    embedding vector(1536)
                )
            """)
            upserted = 0
            for doc in documents:
                content = doc.get("content") or doc.get("text", "")
                meta = doc.get("metadata", {})
                doc_id = doc.get("id") or str(abs(hash(content)))
                vec = await _embed(content, embed_provider, embed_model)
                import json as _json
                await conn.execute(
                    f"INSERT INTO {table} (id, content, metadata, embedding) VALUES ($1, $2, $3::jsonb, $4::vector) ON CONFLICT (id) DO UPDATE SET content=EXCLUDED.content, metadata=EXCLUDED.metadata, embedding=EXCLUDED.embedding",
                    doc_id, content, _json.dumps(meta), str(vec),
                )
                upserted += 1
        finally:
            await conn.close()
        return {"upserted": upserted, "table": table}
    except ImportError:
        raise ImportError("vectorstore.postgres requires asyncpg: pip install asyncpg")

@register_node("vectorstore.postgres.query")
async def vs_postgres_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    conn_str = config.get("connection_string") or getattr(settings, "DATABASE_URL", "")
    table = config.get("table_name", "vector_documents")
    query = config.get("query") or input_data.get("query", "")
    top_k = int(config.get("top_k", 4))
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")
    vec = await _embed(query, embed_provider, embed_model)
    try:
        import asyncpg, json as _json
        dsn = conn_str.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://")
        conn = await asyncpg.connect(dsn)
        try:
            rows = await conn.fetch(
                f"SELECT id, content, metadata, 1 - (embedding <=> $1::vector) AS score FROM {table} ORDER BY embedding <=> $1::vector LIMIT $2",
                str(vec), top_k,
            )
            results = [{"id": r["id"], "content": r["content"], "score": float(r["score"]), "metadata": _json.loads(r["metadata"]) if r["metadata"] else {}} for r in rows]
        finally:
            await conn.close()
        return {"results": results, "query": query, "table": table}
    except ImportError:
        raise ImportError("vectorstore.postgres requires asyncpg: pip install asyncpg")

@register_node("vectorstore.postgres.delete")
async def vs_postgres_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    conn_str = config.get("connection_string") or getattr(settings, "DATABASE_URL", "")
    table = config.get("table_name", "vector_documents")
    doc_id = config.get("id") or input_data.get("id")
    try:
        import asyncpg
        dsn = conn_str.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://")
        conn = await asyncpg.connect(dsn)
        try:
            if doc_id:
                await conn.execute(f"DELETE FROM {table} WHERE id = $1", doc_id)
            else:
                await conn.execute(f"TRUNCATE {table}")
        finally:
            await conn.close()
        return {"deleted": True, "table": table}
    except ImportError:
        raise ImportError("vectorstore.postgres requires asyncpg: pip install asyncpg")


# ─── Redis Vector Store ───────────────────────────────────────────────────────

@register_node("vectorstore.redis_vs.upsert")
async def vs_redis_vs_upsert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Vector search via Redis Stack using RediSearch."""
    import json as _json, struct
    redis_url = config.get("redis_url") or getattr(settings, "REDIS_VS_URL", None) or getattr(settings, "REDIS_URL", "redis://localhost:6379")
    index_name = config.get("index_name", "idx:vectors")
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")
    documents = input_data.get("documents", [])
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(redis_url)
        # Create index if not exists
        try:
            await r.execute_command("FT.CREATE", index_name, "ON", "HASH", "PREFIX", "1", "doc:", "SCHEMA", "content", "TEXT", "embedding", "VECTOR", "FLAT", "6", "TYPE", "FLOAT32", "DIM", "1536", "DISTANCE_METRIC", "COSINE")
        except Exception:
            pass  # Index may already exist
        upserted = 0
        for doc in documents:
            content = doc.get("content") or doc.get("text", "")
            meta = doc.get("metadata", {})
            doc_id = doc.get("id") or str(abs(hash(content)))
            vec = await _embed(content, embed_provider, embed_model)
            vec_bytes = struct.pack(f"{len(vec)}f", *vec)
            await r.hset(f"doc:{doc_id}", mapping={"content": content, "metadata": _json.dumps(meta), "embedding": vec_bytes})
            upserted += 1
        await r.aclose()
        return {"upserted": upserted, "index": index_name}
    except ImportError:
        raise ImportError("vectorstore.redis_vs requires redis[hiredis]: pip install redis[hiredis]")

@register_node("vectorstore.redis_vs.query")
async def vs_redis_vs_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    import struct, json as _json
    redis_url = config.get("redis_url") or getattr(settings, "REDIS_VS_URL", None) or getattr(settings, "REDIS_URL", "redis://localhost:6379")
    index_name = config.get("index_name", "idx:vectors")
    query = config.get("query") or input_data.get("query", "")
    top_k = int(config.get("top_k", 4))
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")
    vec = await _embed(query, embed_provider, embed_model)
    vec_bytes = struct.pack(f"{len(vec)}f", *vec)
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(redis_url)
        results_raw = await r.execute_command(
            "FT.SEARCH", index_name, f"*=>[KNN {top_k} @embedding $BLOB AS score]",
            "PARAMS", "2", "BLOB", vec_bytes, "SORTBY", "score", "LIMIT", "0", top_k, "RETURN", "3", "content", "metadata", "score",
        )
        await r.aclose()
        results = []
        # Parse results (format: [total, key, [field,val,...], key, ...])
        if results_raw and len(results_raw) > 1:
            items = results_raw[1:]
            for i in range(0, len(items), 2):
                key = items[i].decode() if isinstance(items[i], bytes) else items[i]
                fields = items[i+1] if i+1 < len(items) else []
                fdict = {}
                for j in range(0, len(fields), 2):
                    k = fields[j].decode() if isinstance(fields[j], bytes) else fields[j]
                    v = fields[j+1].decode() if isinstance(fields[j+1], bytes) else fields[j+1]
                    fdict[k] = v
                results.append({
                    "id": key.replace("doc:", ""),
                    "content": fdict.get("content", ""),
                    "score": float(fdict.get("score", 0)),
                    "metadata": _json.loads(fdict.get("metadata", "{}")),
                })
        return {"results": results, "query": query, "index": index_name}
    except ImportError:
        raise ImportError("vectorstore.redis_vs requires redis: pip install redis[hiredis]")

@register_node("vectorstore.redis_vs.delete")
async def vs_redis_vs_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    redis_url = config.get("redis_url") or getattr(settings, "REDIS_VS_URL", None) or getattr(settings, "REDIS_URL", "redis://localhost:6379")
    doc_id = config.get("id") or input_data.get("id")
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(redis_url)
        if doc_id:
            await r.delete(f"doc:{doc_id}")
        await r.aclose()
        return {"deleted": True}
    except ImportError:
        raise ImportError("vectorstore.redis_vs requires redis: pip install redis[hiredis]")


# ─── Simple File-backed Store ─────────────────────────────────────────────────

import json as _json_simple
_SIMPLE_STORE_CACHE: dict = {}

@register_node("vectorstore.simple.upsert")
async def vs_simple_upsert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Simple file-backed vector store for development/testing."""
    storage_path = config.get("storage_path", "/tmp/autoflow_simple_vs.json")
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")
    documents = input_data.get("documents", [])
    # Load existing store
    import os
    if storage_path not in _SIMPLE_STORE_CACHE:
        if os.path.exists(storage_path):
            with open(storage_path) as f:
                _SIMPLE_STORE_CACHE[storage_path] = _json_simple.load(f)
        else:
            _SIMPLE_STORE_CACHE[storage_path] = []
    store = _SIMPLE_STORE_CACHE[storage_path]
    upserted = 0
    for doc in documents:
        content = doc.get("content") or doc.get("text", "")
        meta = doc.get("metadata", {})
        doc_id = doc.get("id") or str(abs(hash(content)))
        vec = await _embed(content, embed_provider, embed_model)
        store = [d for d in store if d["id"] != doc_id]
        store.append({"id": doc_id, "content": content, "metadata": meta, "embedding": vec})
        upserted += 1
    _SIMPLE_STORE_CACHE[storage_path] = store
    with open(storage_path, "w") as f:
        _json_simple.dump(store, f)
    return {"upserted": upserted, "storage_path": storage_path, "total": len(store)}

@register_node("vectorstore.simple.query")
async def vs_simple_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    storage_path = config.get("storage_path", "/tmp/autoflow_simple_vs.json")
    query = config.get("query") or input_data.get("query", "")
    top_k = int(config.get("top_k", 4))
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")
    import os
    if storage_path not in _SIMPLE_STORE_CACHE:
        if os.path.exists(storage_path):
            with open(storage_path) as f:
                _SIMPLE_STORE_CACHE[storage_path] = _json_simple.load(f)
        else:
            _SIMPLE_STORE_CACHE[storage_path] = []
    store = _SIMPLE_STORE_CACHE[storage_path]
    if not store:
        return {"results": [], "query": query}
    qvec = await _embed(query, embed_provider, embed_model)
    scored = [(d, _cosine(qvec, d["embedding"])) for d in store]
    scored.sort(key=lambda x: x[1], reverse=True)
    results = [{"id": d["id"], "content": d["content"], "score": s, "metadata": d.get("metadata", {})} for d, s in scored[:top_k]]
    return {"results": results, "query": query}

@register_node("vectorstore.simple.delete")
async def vs_simple_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    storage_path = config.get("storage_path", "/tmp/autoflow_simple_vs.json")
    doc_id = config.get("id") or input_data.get("id")
    if storage_path in _SIMPLE_STORE_CACHE:
        store = _SIMPLE_STORE_CACHE[storage_path]
        if doc_id:
            store = [d for d in store if d["id"] != doc_id]
        else:
            store = []
        _SIMPLE_STORE_CACHE[storage_path] = store
        with open(storage_path, "w") as f:
            _json_simple.dump(store, f)
    return {"deleted": True, "storage_path": storage_path}


# ─── Couchbase ────────────────────────────────────────────────────────────────

@register_node("vectorstore.couchbase.upsert")
async def vs_couchbase_upsert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Upsert into Couchbase vector search via SDK."""
    conn_str = config.get("connection_string") or getattr(settings, "COUCHBASE_CONNECTION_STRING", None)
    username = config.get("username") or getattr(settings, "COUCHBASE_USERNAME", None)
    password = config.get("password") or getattr(settings, "COUCHBASE_PASSWORD", None)
    if not conn_str or not username or not password:
        raise ValueError("vectorstore.couchbase requires COUCHBASE_CONNECTION_STRING, COUCHBASE_USERNAME, COUCHBASE_PASSWORD")
    bucket_name = config.get("bucket", "default")
    scope_name = config.get("scope", "_default")
    collection_name = config.get("collection", "_default")
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")
    documents = input_data.get("documents", [])
    try:
        from couchbase.cluster import Cluster
        from couchbase.auth import PasswordAuthenticator
        from couchbase.options import ClusterOptions
        import asyncio
        upserted = 0
        def _do_upsert():
            cluster = Cluster(conn_str, ClusterOptions(PasswordAuthenticator(username, password)))
            bucket = cluster.bucket(bucket_name)
            col = bucket.scope(scope_name).collection(collection_name)
            count = 0
            for doc in documents:
                content = doc.get("content") or doc.get("text", "")
                meta = doc.get("metadata", {})
                doc_id = doc.get("id") or str(abs(hash(content)))
                col.upsert(doc_id, {"content": content, "metadata": meta})
                count += 1
            return count
        loop = asyncio.get_event_loop()
        upserted = await loop.run_in_executor(None, _do_upsert)
        return {"upserted": upserted, "bucket": bucket_name}
    except ImportError:
        raise ImportError("vectorstore.couchbase requires couchbase SDK: pip install couchbase")

@register_node("vectorstore.couchbase.query")
async def vs_couchbase_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Query Couchbase full-text search (FTS) index."""
    conn_str = config.get("connection_string") or getattr(settings, "COUCHBASE_CONNECTION_STRING", None)
    username = config.get("username") or getattr(settings, "COUCHBASE_USERNAME", None)
    password = config.get("password") or getattr(settings, "COUCHBASE_PASSWORD", None)
    if not conn_str or not username or not password:
        raise ValueError("vectorstore.couchbase requires COUCHBASE_CONNECTION_STRING, COUCHBASE_USERNAME, COUCHBASE_PASSWORD")
    query_text = config.get("query") or input_data.get("query", "")
    top_k = int(config.get("top_k", 4))
    index_name = config.get("index_name", "vector_index")
    try:
        from couchbase.cluster import Cluster
        from couchbase.auth import PasswordAuthenticator
        from couchbase.options import ClusterOptions, SearchOptions
        from couchbase.search import SearchRequest
        import couchbase.search as search
        import asyncio
        def _do_search():
            cluster = Cluster(conn_str, ClusterOptions(PasswordAuthenticator(username, password)))
            result = cluster.search(index_name, SearchRequest.create(search.MatchQuery(query_text)), SearchOptions(limit=top_k, fields=["content", "metadata"]))
            return [{"id": r.id, "content": r.fields.get("content", ""), "score": r.score, "metadata": r.fields.get("metadata", {})} for r in result.rows()]
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, _do_search)
        return {"results": results, "query": query_text}
    except ImportError:
        raise ImportError("vectorstore.couchbase requires couchbase SDK: pip install couchbase")

@register_node("vectorstore.couchbase.delete")
async def vs_couchbase_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    conn_str = config.get("connection_string") or getattr(settings, "COUCHBASE_CONNECTION_STRING", None)
    username = config.get("username") or getattr(settings, "COUCHBASE_USERNAME", None)
    password = config.get("password") or getattr(settings, "COUCHBASE_PASSWORD", None)
    if not conn_str or not username or not password:
        raise ValueError("vectorstore.couchbase requires credentials")
    doc_id = config.get("id") or input_data.get("id")
    if not doc_id:
        return {"deleted": False, "error": "No document ID provided"}
    try:
        from couchbase.cluster import Cluster
        from couchbase.auth import PasswordAuthenticator
        from couchbase.options import ClusterOptions
        import asyncio
        def _do_delete():
            cluster = Cluster(conn_str, ClusterOptions(PasswordAuthenticator(username, password)))
            bucket = cluster.bucket(config.get("bucket", "default"))
            col = bucket.scope(config.get("scope", "_default")).collection(config.get("collection", "_default"))
            col.remove(doc_id)
        await asyncio.get_event_loop().run_in_executor(None, _do_delete)
        return {"deleted": True, "id": doc_id}
    except ImportError:
        raise ImportError("vectorstore.couchbase requires couchbase SDK")


# ─── DocumentStore VS ─────────────────────────────────────────────────────────

@register_node("vectorstore.docstore.upsert")
async def vs_docstore_upsert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Upsert into the platform's internal vector document store."""
    from storage.models import VectorDocument
    import json as _json
    store_id = config.get("store_id") or input_data.get("store_id", "default")
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")
    documents = input_data.get("documents", [])
    upserted = 0
    for doc in documents:
        content = doc.get("content") or doc.get("text", "")
        meta = doc.get("metadata", {})
        doc_id = doc.get("id") or str(abs(hash(content)))
        vec = await _embed(content, embed_provider, embed_model)
        try:
            vdoc = VectorDocument(id=doc_id, store_id=store_id, content=content, metadata=meta, embedding=vec)
            db.add(vdoc)
            upserted += 1
        except Exception as e:
            log.warning("docstore_upsert_error", error=str(e))
    return {"upserted": upserted, "store_id": store_id}

@register_node("vectorstore.docstore.query")
async def vs_docstore_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Query the platform's internal vector document store."""
    from storage.models import VectorDocument
    from sqlalchemy import select
    store_id = config.get("store_id") or input_data.get("store_id")
    query = config.get("query") or input_data.get("query", "")
    top_k = int(config.get("top_k", 4))
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")
    qvec = await _embed(query, embed_provider, embed_model)
    q = select(VectorDocument)
    if store_id:
        q = q.where(VectorDocument.store_id == store_id)
    result = await db.execute(q)
    all_docs = result.scalars().all()
    scored = [(d, _cosine(qvec, d.embedding)) for d in all_docs if d.embedding]
    scored.sort(key=lambda x: x[1], reverse=True)
    results = [{"id": str(d.id), "content": d.content, "score": s, "metadata": d.metadata or {}} for d, s in scored[:top_k]]
    return {"results": results, "query": query, "store_id": store_id}

@register_node("vectorstore.docstore.delete")
async def vs_docstore_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    from storage.models import VectorDocument
    doc_id = config.get("id") or input_data.get("id")
    if doc_id:
        from sqlalchemy import delete
        await db.execute(delete(VectorDocument).where(VectorDocument.id == doc_id))
    return {"deleted": True}


# ─── Kendra (AWS) ────────────────────────────────────────────────────────────

@register_node("vectorstore.kendra.query")
async def vs_kendra_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    index_id = config.get("index_id") or getattr(settings, "KENDRA_INDEX_ID", None)
    if not index_id:
        raise ValueError("vectorstore.kendra requires KENDRA_INDEX_ID")
    query = config.get("query") or input_data.get("query", "")
    top_k = int(config.get("top_k", 4))
    try:
        import boto3, asyncio
        def _do_query():
            client = boto3.client("kendra", region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None)
            return client.query(IndexId=index_id, QueryText=query, PageSize=top_k)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, _do_query)
        items = response.get("ResultItems", [])
        results = [{"id": it.get("Id"), "content": it.get("DocumentExcerpt", {}).get("Text", ""), "score": it.get("ScoreAttributes", {}).get("ScoreConfidence", ""), "metadata": {"title": it.get("DocumentTitle", {}).get("Text", ""), "uri": it.get("DocumentURI", "")}} for it in items[:top_k]]
        return {"results": results, "query": query, "index_id": index_id}
    except ImportError:
        raise ImportError("vectorstore.kendra requires boto3: pip install boto3")

@register_node("vectorstore.kendra.upsert")
async def vs_kendra_upsert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    index_id = config.get("index_id") or getattr(settings, "KENDRA_INDEX_ID", None)
    if not index_id:
        raise ValueError("vectorstore.kendra requires KENDRA_INDEX_ID")
    documents = input_data.get("documents", [])
    try:
        import boto3, asyncio
        def _do_upsert():
            client = boto3.client("kendra", region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None)
            docs = []
            for doc in documents:
                content = doc.get("content") or doc.get("text", "")
                doc_id = doc.get("id") or str(abs(hash(content)))
                docs.append({"Id": doc_id, "Title": doc.get("metadata", {}).get("title", doc_id), "Blob": content.encode()})
            return client.batch_put_document(IndexId=index_id, Documents=docs)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, _do_upsert)
        return {"upserted": len(documents), "index_id": index_id}
    except ImportError:
        raise ImportError("vectorstore.kendra requires boto3: pip install boto3")

@register_node("vectorstore.kendra.delete")
async def vs_kendra_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    index_id = config.get("index_id") or getattr(settings, "KENDRA_INDEX_ID", None)
    if not index_id:
        raise ValueError("vectorstore.kendra requires KENDRA_INDEX_ID")
    doc_ids = config.get("ids") or ([config.get("id")] if config.get("id") else [])
    if not doc_ids:
        return {"deleted": 0}
    try:
        import boto3, asyncio
        def _do_delete():
            client = boto3.client("kendra", region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None)
            return client.batch_delete_document(IndexId=index_id, DocumentIdList=doc_ids)
        await asyncio.get_event_loop().run_in_executor(None, _do_delete)
        return {"deleted": len(doc_ids), "index_id": index_id}
    except ImportError:
        raise ImportError("vectorstore.kendra requires boto3: pip install boto3")


# ─── Singlestore ──────────────────────────────────────────────────────────────

@register_node("vectorstore.singlestore.upsert")
async def vs_singlestore_upsert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    singlestore_url = config.get("url") or getattr(settings, "SINGLESTORE_URL", None)
    if not singlestore_url:
        raise ValueError("vectorstore.singlestore requires SINGLESTORE_URL (MySQL-compatible DSN)")
    table = config.get("table_name", "vector_store")
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")
    documents = input_data.get("documents", [])
    try:
        import aiomysql, asyncio, json as _json
        # Parse DSN: mysql://user:pass@host:port/db
        import re as _re
        m = _re.match(r"mysql\+?[^:]*://([^:]+):([^@]*)@([^:/]+):?(\d+)?/(\w+)", singlestore_url)
        if not m:
            raise ValueError("Invalid SINGLESTORE_URL format")
        user, pwd, host, port, db_name = m.group(1), m.group(2), m.group(3), int(m.group(4) or 3306), m.group(5)
        conn = await aiomysql.connect(host=host, port=port, user=user, password=pwd, db=db_name)
        async with conn.cursor() as cur:
            await cur.execute(f"CREATE TABLE IF NOT EXISTS {table} (id VARCHAR(255) PRIMARY KEY, content TEXT, embedding JSON, metadata JSON)")
            upserted = 0
            for doc in documents:
                content = doc.get("content") or doc.get("text", "")
                meta = doc.get("metadata", {})
                doc_id = doc.get("id") or str(abs(hash(content)))
                vec = await _embed(content, embed_provider, embed_model)
                await cur.execute(f"REPLACE INTO {table} (id, content, embedding, metadata) VALUES (%s, %s, %s, %s)", (doc_id, content, _json.dumps(vec), _json.dumps(meta)))
                upserted += 1
        await conn.commit()
        conn.close()
        return {"upserted": upserted, "table": table}
    except ImportError:
        raise ImportError("vectorstore.singlestore requires aiomysql: pip install aiomysql")

@register_node("vectorstore.singlestore.query")
async def vs_singlestore_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    singlestore_url = config.get("url") or getattr(settings, "SINGLESTORE_URL", None)
    if not singlestore_url:
        raise ValueError("vectorstore.singlestore requires SINGLESTORE_URL")
    table = config.get("table_name", "vector_store")
    query = config.get("query") or input_data.get("query", "")
    top_k = int(config.get("top_k", 4))
    embed_provider = config.get("embed_provider", "openai")
    embed_model = config.get("embed_model", "text-embedding-3-small")
    vec = await _embed(query, embed_provider, embed_model)
    try:
        import aiomysql, json as _json, re as _re
        m = _re.match(r"mysql\+?[^:]*://([^:]+):([^@]*)@([^:/]+):?(\d+)?/(\w+)", singlestore_url)
        if not m:
            raise ValueError("Invalid SINGLESTORE_URL format")
        user, pwd, host, port, db_name = m.group(1), m.group(2), m.group(3), int(m.group(4) or 3306), m.group(5)
        conn = await aiomysql.connect(host=host, port=port, user=user, password=pwd, db=db_name)
        vec_str = "[" + ",".join(str(v) for v in vec) + "]"
        async with conn.cursor() as cur:
            await cur.execute(f"SELECT id, content, metadata, DOT_PRODUCT(embedding, '{vec_str}') AS similarity FROM {table} ORDER BY similarity DESC LIMIT %s", (top_k,))
            rows = await cur.fetchall()
        conn.close()
        results = [{"id": r[0], "content": r[1], "score": float(r[3]), "metadata": _json.loads(r[2]) if r[2] else {}} for r in rows]
        return {"results": results, "query": query}
    except ImportError:
        raise ImportError("vectorstore.singlestore requires aiomysql: pip install aiomysql")

@register_node("vectorstore.singlestore.delete")
async def vs_singlestore_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    singlestore_url = config.get("url") or getattr(settings, "SINGLESTORE_URL", None)
    if not singlestore_url:
        raise ValueError("vectorstore.singlestore requires SINGLESTORE_URL")
    table = config.get("table_name", "vector_store")
    doc_id = config.get("id") or input_data.get("id")
    try:
        import aiomysql, re as _re
        m = _re.match(r"mysql\+?[^:]*://([^:]+):([^@]*)@([^:/]+):?(\d+)?/(\w+)", singlestore_url)
        user, pwd, host, port, db_name = m.group(1), m.group(2), m.group(3), int(m.group(4) or 3306), m.group(5)
        conn = await aiomysql.connect(host=host, port=port, user=user, password=pwd, db=db_name)
        async with conn.cursor() as cur:
            if doc_id:
                await cur.execute(f"DELETE FROM {table} WHERE id = %s", (doc_id,))
            else:
                await cur.execute(f"TRUNCATE {table}")
        await conn.commit()
        conn.close()
        return {"deleted": True}
    except ImportError:
        raise ImportError("vectorstore.singlestore requires aiomysql: pip install aiomysql")
