"""Plausible privacy analytics integration — stats, timeseries, breakdown, and sites."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

PLAUSIBLE_BASE = "https://plausible.io/api/v1"


def _headers(config: dict, input_data: dict) -> dict:
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required")
    return {"Authorization": f"Bearer {api_key}"}


@register_node("plausible.get_stats")
async def plausible_get_stats(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Fetch aggregate statistics for a Plausible site.

    config:
      api_key  — Plausible API key (required)
      site_id  — site domain as registered in Plausible (required)
      period   — time period (default '30d')
      metrics  — comma-separated metrics (default 'visitors,pageviews')
    """
    headers = _headers(config, input_data)
    site_id = config.get("site_id") or input_data.get("site_id")
    if not site_id:
        raise ValueError("site_id is required")
    period = config.get("period", "30d")
    metrics = config.get("metrics", "visitors,pageviews")

    params = {"site_id": site_id, "period": period, "metrics": metrics}

    async with httpx.AsyncClient(base_url=PLAUSIBLE_BASE, headers=headers, timeout=30) as client:
        r = await client.get("/stats/aggregate", params=params)
        r.raise_for_status()
        data = r.json()

    log.info("plausible.get_stats", site_id=site_id, period=period)
    return {"stats": data, "site_id": site_id, "period": period}


@register_node("plausible.get_timeseries")
async def plausible_get_timeseries(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Fetch timeseries data for a Plausible site.

    config:
      api_key — Plausible API key (required)
      site_id — site domain (required)
      period  — time period (default '30d')
    """
    headers = _headers(config, input_data)
    site_id = config.get("site_id") or input_data.get("site_id")
    if not site_id:
        raise ValueError("site_id is required")
    period = config.get("period", "30d")

    params = {"site_id": site_id, "period": period}

    async with httpx.AsyncClient(base_url=PLAUSIBLE_BASE, headers=headers, timeout=30) as client:
        r = await client.get("/stats/timeseries", params=params)
        r.raise_for_status()
        data = r.json()

    log.info("plausible.get_timeseries", site_id=site_id, period=period)
    return {"timeseries": data, "site_id": site_id, "period": period}


@register_node("plausible.get_breakdown")
async def plausible_get_breakdown(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Fetch a property breakdown for a Plausible site.

    config:
      api_key  — Plausible API key (required)
      site_id  — site domain (required)
      property — breakdown property (default 'event:page')
      period   — time period (default '30d')
    """
    headers = _headers(config, input_data)
    site_id = config.get("site_id") or input_data.get("site_id")
    if not site_id:
        raise ValueError("site_id is required")
    prop = config.get("property", "event:page")
    period = config.get("period", "30d")

    params = {"site_id": site_id, "property": prop, "period": period}

    async with httpx.AsyncClient(base_url=PLAUSIBLE_BASE, headers=headers, timeout=30) as client:
        r = await client.get("/stats/breakdown", params=params)
        r.raise_for_status()
        data = r.json()

    log.info("plausible.get_breakdown", site_id=site_id, property=prop)
    return {"breakdown": data, "site_id": site_id, "property": prop, "period": period}


@register_node("plausible.list_sites")
async def plausible_list_sites(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all sites in a Plausible account.

    config:
      api_key — Plausible API key (required)
    """
    headers = _headers(config, input_data)

    async with httpx.AsyncClient(base_url=PLAUSIBLE_BASE, headers=headers, timeout=30) as client:
        r = await client.get("/sites")
        r.raise_for_status()
        data = r.json()

    sites = data if isinstance(data, list) else data.get("sites", [])
    log.info("plausible.list_sites", count=len(sites))
    return {"sites": sites, "count": len(sites)}
