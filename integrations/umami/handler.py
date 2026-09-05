"""Umami self-hosted analytics integration — websites, stats, and pageviews."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _base_url(config: dict) -> str:
    host = config.get("host", "")
    if not host:
        raise ValueError("host is required in config")
    return f"https://{host}/api"


def _headers(config: dict, input_data: dict) -> dict:
    token = config.get("token") or input_data.get("token")
    if not token:
        raise ValueError("token is required (use POST /auth/login to obtain one)")
    return {"Authorization": f"Bearer {token}"}


@register_node("umami.list_websites")
async def umami_list_websites(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all websites tracked in Umami.

    config:
      host  — Umami host (e.g. 'umami.example.com') (required)
      token — Bearer token from /auth/login (required)
    """
    base = _base_url(config)
    headers = _headers(config, input_data)

    async with httpx.AsyncClient(base_url=base, headers=headers, timeout=30) as client:
        r = await client.get("/websites")
        r.raise_for_status()
        data = r.json()

    websites = data if isinstance(data, list) else data.get("data", [])
    log.info("umami.list_websites", count=len(websites))
    return {"websites": websites, "count": len(websites)}


@register_node("umami.get_website_stats")
async def umami_get_website_stats(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get stats for a specific Umami website.

    config/input_data:
      host       — Umami host (required)
      token      — Bearer token (required)
      website_id — UUID of the website (required)
      start_at   — start timestamp in milliseconds (required)
      end_at     — end timestamp in milliseconds (required)
    """
    base = _base_url(config)
    headers = _headers(config, input_data)
    website_id = config.get("website_id") or input_data.get("website_id")
    if not website_id:
        raise ValueError("website_id is required")
    start_at = config.get("start_at") or input_data.get("start_at")
    end_at = config.get("end_at") or input_data.get("end_at")
    if not start_at or not end_at:
        raise ValueError("start_at and end_at are required (millisecond timestamps)")

    params = {"startAt": start_at, "endAt": end_at}

    async with httpx.AsyncClient(base_url=base, headers=headers, timeout=30) as client:
        r = await client.get(f"/websites/{website_id}/stats", params=params)
        r.raise_for_status()
        data = r.json()

    log.info("umami.get_website_stats", website_id=website_id)
    return {"stats": data, "website_id": website_id}


@register_node("umami.get_pageviews")
async def umami_get_pageviews(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get pageview data for a specific Umami website.

    config/input_data:
      host       — Umami host (required)
      token      — Bearer token (required)
      website_id — UUID of the website (required)
      start_at   — start timestamp in milliseconds (required)
      end_at     — end timestamp in milliseconds (required)
      unit       — grouping unit: 'day', 'hour', etc. (default 'day')
    """
    base = _base_url(config)
    headers = _headers(config, input_data)
    website_id = config.get("website_id") or input_data.get("website_id")
    if not website_id:
        raise ValueError("website_id is required")
    start_at = config.get("start_at") or input_data.get("start_at")
    end_at = config.get("end_at") or input_data.get("end_at")
    if not start_at or not end_at:
        raise ValueError("start_at and end_at are required (millisecond timestamps)")
    unit = config.get("unit", "day")

    params = {"startAt": start_at, "endAt": end_at, "unit": unit}

    async with httpx.AsyncClient(base_url=base, headers=headers, timeout=30) as client:
        r = await client.get(f"/websites/{website_id}/pageviews", params=params)
        r.raise_for_status()
        data = r.json()

    log.info("umami.get_pageviews", website_id=website_id, unit=unit)
    return {"pageviews": data, "website_id": website_id, "unit": unit}
