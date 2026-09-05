"""Pinecone vector database integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

PINECONE_CONTROL_BASE = "https://api.pinecone.io"


@register_node("pinecone.upsert")
async def pinecone_upsert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Upsert vectors into a Pinecone index.

    config/input_data:
      api_key    — Pinecone API key
      index_host — full host URL of the Pinecone index (e.g. https://my-index-xxx.svc.pinecone.io)
      vectors    — list of {"id": str, "values": [...]} dicts
      namespace  — optional namespace string (default "")
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    index_host = merged.get("index_host") or ""
    vectors = merged.get("vectors") or []
    namespace = merged.get("namespace") or ""

    headers = {"Api-Key": api_key, "Content-Type": "application/json"}
    payload = {"vectors": vectors, "namespace": namespace}

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{index_host}/vectors/upsert", headers=headers, json=payload)
        r.raise_for_status()

    result = r.json()
    log.info("pinecone.upsert", upserted_count=result.get("upsertedCount"))
    return {"result": result}


@register_node("pinecone.query")
async def pinecone_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Query a Pinecone index for nearest vectors.

    config/input_data:
      api_key          — Pinecone API key
      index_host       — full host URL of the Pinecone index
      vector           — query vector as a list of floats
      top_k            — number of results to return (default 10)
      namespace        — optional namespace string (default "")
      include_metadata — include metadata in results (default True)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    index_host = merged.get("index_host") or ""
    vector = merged.get("vector") or []
    top_k = int(merged.get("top_k", 10))
    namespace = merged.get("namespace") or ""
    include_metadata = bool(merged.get("include_metadata", True))

    headers = {"Api-Key": api_key, "Content-Type": "application/json"}
    payload = {
        "vector": vector,
        "topK": top_k,
        "namespace": namespace,
        "includeMetadata": include_metadata,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{index_host}/query", headers=headers, json=payload)
        r.raise_for_status()

    result = r.json()
    log.info("pinecone.query", match_count=len(result.get("matches", [])))
    return {"result": result}


@register_node("pinecone.delete")
async def pinecone_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete vectors from a Pinecone index by ID.

    config/input_data:
      api_key    — Pinecone API key
      index_host — full host URL of the Pinecone index
      ids        — list of vector IDs to delete
      namespace  — optional namespace string (default "")
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    index_host = merged.get("index_host") or ""
    ids = merged.get("ids") or []
    namespace = merged.get("namespace") or ""

    headers = {"Api-Key": api_key, "Content-Type": "application/json"}
    payload = {"ids": ids, "namespace": namespace}

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{index_host}/vectors/delete", headers=headers, json=payload)
        r.raise_for_status()

    result = r.json()
    log.info("pinecone.delete", ids_count=len(ids))
    return {"result": result}


@register_node("pinecone.list_indexes")
async def pinecone_list_indexes(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Pinecone indexes.

    config/input_data:
      api_key — Pinecone API key
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""

    headers = {"Api-Key": api_key}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{PINECONE_CONTROL_BASE}/indexes", headers=headers)
        r.raise_for_status()

    result = r.json()
    log.info("pinecone.list_indexes", count=len(result.get("indexes", [])))
    return {"result": result}
