"""Valyu AI-powered data marketplace — handler for valyu integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.valyu.network/v1"


@register_node("valyu.search")
async def valyu_search(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Search the data marketplace.

    config/input_data:
      api_key — API key or token (required)
      query — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    query = merged.get("query") or ""
    if not query:
        raise ValueError("query required for valyu.search")
    payload = {"query": query}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/search", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("valyu.search")
    return {"data": data}

@register_node("valyu.list_datasets")
async def valyu_list_datasets(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List datasets.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/datasets", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("valyu.list_datasets")
    return {"data": data}
