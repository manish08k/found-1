"""
Airtop AI browser automation integration.

Provides browser session management, page scraping, and structured
data extraction via the Airtop API v1.

Credential fields:
  - api_key : Airtop API key

Auth: Bearer token.
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://api.airtop.ai/v1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Airtop credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=120.0,  # Browser operations can take longer
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Airtop API error {r.status_code}: {detail}")


@register_node("airtop.create_session")
async def airtop_create_session(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new Airtop browser session."""
    configuration = config.get("configuration") or input_data.get("configuration", {})

    # Optional session settings
    browser_type = config.get("browser_type") or input_data.get("browser_type", "chrome")
    headless = config.get("headless") if "headless" in config else input_data.get("headless", True)
    timeout_minutes = int(config.get("timeout_minutes") or input_data.get("timeout_minutes", 10))
    viewport_width = int(config.get("viewport_width") or input_data.get("viewport_width", 1280))
    viewport_height = int(config.get("viewport_height") or input_data.get("viewport_height", 800))

    payload: dict = {
        "configuration": {
            "browserType": browser_type,
            "headless": headless,
            "timeoutMinutes": timeout_minutes,
            "viewport": {
                "width": viewport_width,
                "height": viewport_height,
            },
            **configuration,
        }
    }

    async with await _client(credential_id, db) as client:
        r = await client.post("/sessions", json=payload)
        _raise_for_status(r)
        data = r.json()

    session_id = data.get("data", {}).get("id") or data.get("id")
    log.info("airtop.create_session", session_id=session_id)
    return {"session": data.get("data", data), "session_id": session_id}


@register_node("airtop.scrape_page")
async def airtop_scrape_page(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Navigate to a URL and scrape its content within an active session."""
    session_id = config.get("session_id") or input_data.get("session_id")
    url = config.get("url") or input_data.get("url")

    if not session_id:
        raise ValueError("airtop.scrape_page requires 'session_id'")
    if not url:
        raise ValueError("airtop.scrape_page requires 'url'")

    wait_for_selector = config.get("wait_for_selector") or input_data.get("wait_for_selector")
    output_format = config.get("output_format") or input_data.get("output_format", "markdown")

    payload: dict = {
        "url": url,
        "outputFormat": output_format,
    }
    if wait_for_selector:
        payload["waitForSelector"] = wait_for_selector

    async with await _client(credential_id, db) as client:
        r = await client.post(f"/sessions/{session_id}/scrape", json=payload)
        _raise_for_status(r)
        data = r.json()

    content = data.get("data", {}).get("content") or data.get("content", "")
    log.info("airtop.scrape_page", session_id=session_id, url=url, content_length=len(content))
    return {
        "content": content,
        "url": url,
        "session_id": session_id,
        "metadata": data.get("data", {}).get("metadata", {}),
    }


@register_node("airtop.extract_data")
async def airtop_extract_data(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Use AI to extract structured data from a page within an active session."""
    session_id = config.get("session_id") or input_data.get("session_id")
    url = config.get("url") or input_data.get("url")
    prompt = config.get("prompt") or input_data.get("prompt")

    if not session_id:
        raise ValueError("airtop.extract_data requires 'session_id'")
    if not url:
        raise ValueError("airtop.extract_data requires 'url'")
    if not prompt:
        raise ValueError("airtop.extract_data requires 'prompt' describing the data to extract")

    schema = config.get("schema") or input_data.get("schema")
    output_format = config.get("output_format") or input_data.get("output_format", "json")

    payload: dict = {
        "url": url,
        "prompt": prompt,
        "outputFormat": output_format,
    }
    if schema:
        payload["schema"] = schema

    async with await _client(credential_id, db) as client:
        r = await client.post(f"/sessions/{session_id}/extract", json=payload)
        _raise_for_status(r)
        data = r.json()

    extracted = data.get("data", {}).get("result") or data.get("result", {})
    log.info("airtop.extract_data", session_id=session_id, url=url)
    return {
        "extracted_data": extracted,
        "session_id": session_id,
        "url": url,
        "raw_response": data.get("data", data),
    }


@register_node("airtop.close_session")
async def airtop_close_session(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Terminate an active Airtop browser session and release resources."""
    session_id = config.get("session_id") or input_data.get("session_id")
    if not session_id:
        raise ValueError("airtop.close_session requires 'session_id'")

    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/sessions/{session_id}")
        _raise_for_status(r)

    log.info("airtop.close_session", session_id=session_id)
    return {"closed": True, "session_id": session_id}


@register_node("airtop.get_session")
async def airtop_get_session(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve status and details of an existing Airtop session."""
    session_id = config.get("session_id") or input_data.get("session_id")
    if not session_id:
        raise ValueError("airtop.get_session requires 'session_id'")

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/sessions/{session_id}")
        _raise_for_status(r)
        data = r.json()

    return {"session": data.get("data", data), "session_id": session_id}
