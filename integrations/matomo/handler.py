"""Matomo web analytics integration — visits, page URLs, and event tracking."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _base_url(config: dict) -> str:
    matomo_url = config.get("matomo_url", "")
    if not matomo_url:
        raise ValueError("matomo_url is required in config")
    return f"https://{matomo_url}/index.php"


def _token(config: dict, input_data: dict) -> str:
    token = config.get("token_auth") or input_data.get("token_auth")
    if not token:
        raise ValueError("token_auth is required")
    return token


@register_node("matomo.get_visits")
async def matomo_get_visits(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Fetch visit summary for a site from Matomo.

    config:
      matomo_url — hostname of the Matomo instance (required)
      token_auth — API token (required)
      site_id    — Matomo site ID (required)
      period     — reporting period (default 'day')
      date       — date string (default 'today')
    """
    base = _base_url(config)
    token = _token(config, input_data)
    site_id = config.get("site_id") or input_data.get("site_id")
    if not site_id:
        raise ValueError("site_id is required")
    period = config.get("period", "day")
    date = config.get("date", "today")

    params = {
        "module": "API",
        "method": "VisitsSummary.get",
        "idSite": site_id,
        "period": period,
        "date": date,
        "format": "JSON",
        "token_auth": token,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(base, params=params)
        r.raise_for_status()
        data = r.json()

    log.info("matomo.get_visits", site_id=site_id, period=period, date=date)
    return {"visits": data, "site_id": site_id, "period": period, "date": date}


@register_node("matomo.get_page_urls")
async def matomo_get_page_urls(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Fetch page URL analytics from Matomo.

    config:
      matomo_url — hostname of the Matomo instance (required)
      token_auth — API token (required)
      site_id    — Matomo site ID (required)
      period     — reporting period (default 'week')
      date       — date string (default 'today')
    """
    base = _base_url(config)
    token = _token(config, input_data)
    site_id = config.get("site_id") or input_data.get("site_id")
    if not site_id:
        raise ValueError("site_id is required")
    period = config.get("period", "week")
    date = config.get("date", "today")

    params = {
        "module": "API",
        "method": "Actions.getPageUrls",
        "idSite": site_id,
        "period": period,
        "date": date,
        "format": "JSON",
        "token_auth": token,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(base, params=params)
        r.raise_for_status()
        data = r.json()

    log.info("matomo.get_page_urls", site_id=site_id, period=period)
    return {"page_urls": data, "site_id": site_id, "period": period, "date": date}


@register_node("matomo.track_event")
async def matomo_track_event(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Track a custom event in Matomo.

    config/input_data:
      matomo_url — hostname of the Matomo instance (required)
      token_auth — API token (required)
      site_id    — Matomo site ID (required)
      category   — event category (required)
      action     — event action (required)
    """
    matomo_url = config.get("matomo_url", "")
    if not matomo_url:
        raise ValueError("matomo_url is required in config")
    token = _token(config, input_data)
    site_id = config.get("site_id") or input_data.get("site_id")
    category = config.get("category") or input_data.get("category")
    action = config.get("action") or input_data.get("action")

    if not site_id:
        raise ValueError("site_id is required")
    if not category:
        raise ValueError("category is required")
    if not action:
        raise ValueError("action is required")

    payload = {
        "idsite": site_id,
        "rec": 1,
        "e_c": category,
        "e_a": action,
        "token_auth": token,
    }

    track_url = f"https://{matomo_url}/matomo.php"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(track_url, json=payload)
        r.raise_for_status()

    log.info("matomo.track_event", site_id=site_id, category=category, action=action)
    return {"tracked": True, "site_id": site_id, "category": category, "action": action}
