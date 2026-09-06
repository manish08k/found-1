"""TotalCMS flat-file content management — handler for totalcms integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.totalcms.co/v1"


@register_node("totalcms.list_content")
async def totalcms_list_content(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all content items.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/content", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("totalcms.list_content")
    return {"data": data}

@register_node("totalcms.get_content")
async def totalcms_get_content(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get content by slug.

    config/input_data:
      api_key — API key or token (required)
      slug — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    slug = merged.get("slug") or ""
    if not slug:
        raise ValueError("slug required for totalcms.get_content")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/content/{slug}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("totalcms.get_content")
    return {"data": data}

@register_node("totalcms.update_content")
async def totalcms_update_content(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update content.

    config/input_data:
      api_key — API key or token (required)
      slug — (required)
      body — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    slug = merged.get("slug") or ""
    body = merged.get("body") or ""
    if not slug or not body:
        raise ValueError("slug, body required for totalcms.update_content")
    payload = {"body": body}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.put(f"{BASE_URL}/content/{slug}", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("totalcms.update_content")
    return {"data": data}
