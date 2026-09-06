"""WebScraping.AI web data extraction — handler for webscraping_ai integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.webscraping.ai"


@register_node("webscraping_ai.get_html")
async def webscraping_ai_get_html(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get page HTML.

    config/input_data:
      api_key — API key or token (required)
      url — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Content-Type": "application/json"}
    # Auth passed as query param: api_key
    url = merged.get("url") or ""
    if not url:
        raise ValueError("url required for webscraping_ai.get_html")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/html", headers=headers, params={"api_key": api_key})
        r.raise_for_status()
        data = r.json()
    log.info("webscraping_ai.get_html")
    return {"data": data}

@register_node("webscraping_ai.get_text")
async def webscraping_ai_get_text(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get page text content.

    config/input_data:
      api_key — API key or token (required)
      url — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Content-Type": "application/json"}
    # Auth passed as query param: api_key
    url = merged.get("url") or ""
    if not url:
        raise ValueError("url required for webscraping_ai.get_text")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/text", headers=headers, params={"api_key": api_key})
        r.raise_for_status()
        data = r.json()
    log.info("webscraping_ai.get_text")
    return {"data": data}

@register_node("webscraping_ai.get_selected")
async def webscraping_ai_get_selected(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get selected elements.

    config/input_data:
      api_key — API key or token (required)
      url — (required)
      selector — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Content-Type": "application/json"}
    # Auth passed as query param: api_key
    url = merged.get("url") or ""
    selector = merged.get("selector") or ""
    if not url or not selector:
        raise ValueError("url, selector required for webscraping_ai.get_selected")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/selected", headers=headers, params={"api_key": api_key})
        r.raise_for_status()
        data = r.json()
    log.info("webscraping_ai.get_selected")
    return {"data": data}
