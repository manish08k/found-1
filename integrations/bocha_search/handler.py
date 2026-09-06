"""Bocha search API — handler for bocha_search integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.bochasearch.com/v1"


@register_node("bocha_search.search")
async def bocha_search_search(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Perform a web search.

    config/input_data:
      api_key — API key or token (required)
      query — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    query = merged.get("query") or ""
    if not query:
        raise ValueError("query required for bocha_search.search")
    payload = {"query": query}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/search", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("bocha_search.search")
    return {"data": data}
