"""LinkupAPI link aggregation service — handler for linkupapi integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.linkupapi.com/v1"


@register_node("linkupapi.list_links")
async def linkupapi_list_links(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
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
    log.info("linkupapi.list_links")
    return {"data": data}

@register_node("linkupapi.create_link")
async def linkupapi_create_link(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a link.

    config/input_data:
      api_key — API key or token (required)
      url — (required)
      title — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    url = merged.get("url") or ""
    title = merged.get("title") or ""
    if not url or not title:
        raise ValueError("url, title required for linkupapi.create_link")
    payload = {"url": url, "title": title}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/links", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("linkupapi.create_link")
    return {"data": data}
