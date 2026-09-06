"""Browserless headless Chrome as a service — handler for browserless integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://chrome.browserless.io"


@register_node("browserless.get_content")
async def browserless_get_content(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get page HTML content.

    config/input_data:
      api_key — API key or token (required)
      url — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Content-Type": "application/json"}
    # Auth passed as query param: token
    url = merged.get("url") or ""
    if not url:
        raise ValueError("url required for browserless.get_content")
    payload = {"url": url}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/content", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("browserless.get_content")
    return {"data": data}

@register_node("browserless.screenshot")
async def browserless_screenshot(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Take a screenshot.

    config/input_data:
      api_key — API key or token (required)
      url — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Content-Type": "application/json"}
    # Auth passed as query param: token
    url = merged.get("url") or ""
    if not url:
        raise ValueError("url required for browserless.screenshot")
    payload = {"url": url}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/screenshot", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("browserless.screenshot")
    return {"data": data}

@register_node("browserless.pdf")
async def browserless_pdf(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Generate PDF from URL.

    config/input_data:
      api_key — API key or token (required)
      url — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Content-Type": "application/json"}
    # Auth passed as query param: token
    url = merged.get("url") or ""
    if not url:
        raise ValueError("url required for browserless.pdf")
    payload = {"url": url}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/pdf", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("browserless.pdf")
    return {"data": data}
