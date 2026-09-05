"""Qdrant vector search integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _qdrant_base_url(config: dict) -> str:
    host = config.get("host") or "localhost"
    port = int(config.get("port", 6333))
    return f"http://{host}:{port}"


def _qdrant_headers(api_key: str) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["api-key"] = api_key
    return headers


@register_node("qdrant.search")
async def qdrant_search(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Search a Qdrant collection for nearest vectors.

    config/input_data:
      host         — Qdrant host (default "localhost")
      port         — Qdrant port (default 6333)
      api_key      — optional API key
      collection   — collection name
      vector       — query vector as a list of floats
      limit        — number of results (default 10)
      with_payload — include payload in results (default True)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    collection = merged.get("collection") or ""
    vector = merged.get("vector") or []
    limit = int(merged.get("limit", 10))
    with_payload = bool(merged.get("with_payload", True))

    base_url = _qdrant_base_url(merged)
    headers = _qdrant_headers(api_key)
    payload = {"vector": vector, "limit": limit, "with_payload": with_payload}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{base_url}/collections/{collection}/points/search",
            headers=headers,
            json=payload,
        )
        r.raise_for_status()

    result = r.json()
    log.info("qdrant.search", collection=collection, result_count=len(result.get("result", [])))
    return {"result": result}


@register_node("qdrant.upsert")
async def qdrant_upsert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Upsert points into a Qdrant collection.

    config/input_data:
      host       — Qdrant host (default "localhost")
      port       — Qdrant port (default 6333)
      api_key    — optional API key
      collection — collection name
      points     — list of {"id": ..., "vector": [...], "payload": {}} dicts
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    collection = merged.get("collection") or ""
    points = merged.get("points") or []

    base_url = _qdrant_base_url(merged)
    headers = _qdrant_headers(api_key)
    payload = {"points": points}

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.put(
            f"{base_url}/collections/{collection}/points",
            headers=headers,
            json=payload,
        )
        r.raise_for_status()

    result = r.json()
    log.info("qdrant.upsert", collection=collection, points_count=len(points))
    return {"result": result}


@register_node("qdrant.list_collections")
async def qdrant_list_collections(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Qdrant collections.

    config/input_data:
      host    — Qdrant host (default "localhost")
      port    — Qdrant port (default 6333)
      api_key — optional API key
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""

    base_url = _qdrant_base_url(merged)
    headers = _qdrant_headers(api_key)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base_url}/collections", headers=headers)
        r.raise_for_status()

    result = r.json()
    log.info("qdrant.list_collections", count=len(result.get("result", {}).get("collections", [])))
    return {"result": result}
