"""
Peekalink URL preview integration.

Auth: api_key via X-Api-Key header.

Credential fields:
  - api_key (str) : Peekalink API key.

Nodes:
  - peekalink.preview_url  : Generate a rich preview for a URL.
  - peekalink.is_supported : Check whether Peekalink supports previewing a URL.

Base URL: https://api.peekalink.io/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://api.peekalink.io/"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Peekalink credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={
            "X-Api-Key": api_key,
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Peekalink API error {r.status_code}: {detail}")


@register_node("peekalink.preview_url")
async def preview_url(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Generate a rich link preview for a given URL.

    Config / input keys:
      - url (str, required) : The URL to preview.

    Returns metadata including title, description, image, type, etc.
    """
    url = config.get("url") or input_data.get("url")
    if not url:
        raise ValueError("peekalink.preview_url requires 'url'")

    log.info("peekalink.preview_url", url=url)
    async with await _client(credential_id, db) as client:
        r = await client.post("/", json={"link": url})
        _raise_for_status(r)
        data = r.json()

    return {
        "url": url,
        "title": data.get("title"),
        "description": data.get("description"),
        "image": data.get("image"),
        "domain": data.get("domain"),
        "type": data.get("type"),
        "name": data.get("name"),
        "media": data.get("media"),
        "redirected": data.get("redirected"),
        "redirected_url": data.get("redirectedUrl"),
        "is_tracked": data.get("isTracked"),
        "raw": data,
    }


@register_node("peekalink.is_supported")
async def is_supported(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Check whether Peekalink can preview a given URL.

    Config / input keys:
      - url (str, required) : The URL to check.

    Returns {"url": ..., "is_supported": bool}.
    """
    url = config.get("url") or input_data.get("url")
    if not url:
        raise ValueError("peekalink.is_supported requires 'url'")

    log.info("peekalink.is_supported", url=url)
    async with await _client(credential_id, db) as client:
        r = await client.post("/is-supported/", json={"link": url})
        _raise_for_status(r)
        data = r.json()

    return {
        "url": url,
        "is_supported": data.get("isSupported", False),
        "raw": data,
    }
