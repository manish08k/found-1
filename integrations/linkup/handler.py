"""Linkup deep web search API — handler for linkup integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.linkup.so/v1"


@register_node("linkup.search")
async def linkup_search(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Perform a deep web search.

    config/input_data:
      api_key — API key or token (required)
      query — (required)
      depth — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    query = merged.get("query") or ""
    depth = merged.get("depth") or ""
    if not query or not depth:
        raise ValueError("query, depth required for linkup.search")
    payload = {"query": query, "depth": depth}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/search", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("linkup.search")
    return {"data": data}
