"""Linka AI link management — handler for linka integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.linka.ai/v1"


@register_node("linka.create_link")
async def linka_create_link(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a short link.

    config/input_data:
      api_key — API key or token (required)
      url — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    url = merged.get("url") or ""
    if not url:
        raise ValueError("url required for linka.create_link")
    payload = {"url": url}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/links", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("linka.create_link")
    return {"data": data}

@register_node("linka.list_links")
async def linka_list_links(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List links.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/links", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("linka.list_links")
    return {"data": data}

@register_node("linka.get_link_stats")
async def linka_get_link_stats(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get link statistics.

    config/input_data:
      api_key — API key or token (required)
      link_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    link_id = merged.get("link_id") or ""
    if not link_id:
        raise ValueError("link_id required for linka.get_link_stats")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/links/{link_id}/stats", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("linka.get_link_stats")
    return {"data": data}
