"""Fathom Analytics integration — sites listing, site details, and aggregations."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

FATHOM_BASE = "https://api.usefathom.com/v1"


def _headers(config: dict, input_data: dict) -> dict:
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required")
    return {"Authorization": f"Bearer {api_key}"}


@register_node("fathom_analytics.list_sites")
async def fathom_list_sites(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Fathom Analytics sites.

    config:
      api_key — Fathom API key (required)
    """
    headers = _headers(config, input_data)

    async with httpx.AsyncClient(base_url=FATHOM_BASE, headers=headers, timeout=30) as client:
        r = await client.get("/sites")
        r.raise_for_status()
        data = r.json()

    sites = data if isinstance(data, list) else data.get("data", [])
    log.info("fathom_analytics.list_sites", count=len(sites))
    return {"sites": sites, "count": len(sites)}


@register_node("fathom_analytics.get_site")
async def fathom_get_site(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single Fathom Analytics site by ID.

    config/input_data:
      api_key — Fathom API key (required)
      id      — site ID (required)
    """
    headers = _headers(config, input_data)
    site_id = config.get("id") or input_data.get("id")
    if not site_id:
        raise ValueError("id is required")

    async with httpx.AsyncClient(base_url=FATHOM_BASE, headers=headers, timeout=30) as client:
        r = await client.get(f"/sites/{site_id}")
        r.raise_for_status()
        data = r.json()

    log.info("fathom_analytics.get_site", site_id=site_id)
    return {"site": data, "id": site_id}


@register_node("fathom_analytics.get_aggregations")
async def fathom_get_aggregations(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Fetch aggregated analytics data for a Fathom site.

    config/input_data:
      api_key    — Fathom API key (required)
      site_id    — entity/site ID (required)
      aggregates — comma-separated aggregates (default 'visits,pageviews')
      date_from  — start date in YYYY-MM-DD format (required)
    """
    headers = _headers(config, input_data)
    site_id = config.get("site_id") or input_data.get("site_id")
    if not site_id:
        raise ValueError("site_id is required")
    aggregates = config.get("aggregates", "visits,pageviews")
    date_from = config.get("date_from") or input_data.get("date_from")
    if not date_from:
        raise ValueError("date_from is required")

    params = {
        "entity_id": site_id,
        "entity": "site",
        "aggregates": aggregates,
        "date_from": date_from,
    }

    async with httpx.AsyncClient(base_url=FATHOM_BASE, headers=headers, timeout=30) as client:
        r = await client.get("/aggregations", params=params)
        r.raise_for_status()
        data = r.json()

    log.info("fathom_analytics.get_aggregations", site_id=site_id, date_from=date_from)
    return {"aggregations": data, "site_id": site_id, "date_from": date_from}
