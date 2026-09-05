"""Mastodon integration — social network via Mastodon API v1."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _base_and_headers(config: dict, input_data: dict) -> tuple:
    """Return (base_url, headers) for Mastodon API calls."""
    merged = {**config, **input_data}
    instance = merged.get("instance", "").rstrip("/")
    access_token = merged.get("access_token", "")
    if not instance:
        raise ValueError("instance is required for Mastodon")
    base_url = f"https://{instance}/api/v1"
    headers = {"Authorization": f"Bearer {access_token}"}
    return base_url, headers


@register_node("mastodon.post_status")
async def post_status(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Post a status (toot) on Mastodon.

    config/input_data:
      instance     — Mastodon instance hostname (e.g. mastodon.social) (required)
      access_token — OAuth access token (required)
      text         — Status text (required)
      visibility   — Visibility: public, unlisted, private, direct (default: public)
    """
    merged = {**config, **input_data}
    base_url, headers = _base_and_headers(config, input_data)
    text = merged.get("text", "") or merged.get("status", "")
    visibility = merged.get("visibility", "public")
    if not text:
        raise ValueError("text is required for mastodon.post_status")
    payload = {"status": text, "visibility": visibility}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{base_url}/statuses", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("mastodon.post_status", visibility=visibility)
    return {"status": data, "id": data.get("id")}


@register_node("mastodon.get_timeline")
async def get_timeline(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Retrieve the home timeline from Mastodon.

    config/input_data:
      instance     — Mastodon instance hostname (required)
      access_token — OAuth access token (required)
    """
    base_url, headers = _base_and_headers(config, input_data)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base_url}/timelines/home", params={"limit": 20}, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("mastodon.get_timeline", count=len(data))
    return {"statuses": data, "count": len(data)}


@register_node("mastodon.get_account")
async def get_account(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get the authenticated Mastodon account info.

    config/input_data:
      instance     — Mastodon instance hostname (required)
      access_token — OAuth access token (required)
    """
    base_url, headers = _base_and_headers(config, input_data)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base_url}/accounts/verify_credentials", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("mastodon.get_account", username=data.get("username"))
    return {"account": data, "username": data.get("username"), "id": data.get("id")}


@register_node("mastodon.search")
async def search(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Search for statuses on Mastodon.

    config/input_data:
      instance     — Mastodon instance hostname (required)
      access_token — OAuth access token (required)
      query        — Search query (required)
    """
    merged = {**config, **input_data}
    query = merged.get("query", "") or merged.get("q", "")
    if not query:
        raise ValueError("query is required for mastodon.search")
    base_url, headers = _base_and_headers(config, input_data)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{base_url}/search",
            params={"q": query, "type": "statuses"},
            headers=headers,
        )
        r.raise_for_status()
        data = r.json()
    statuses = data.get("statuses", [])
    log.info("mastodon.search", query=query, count=len(statuses))
    return {"statuses": statuses, "count": len(statuses), "query": query}
