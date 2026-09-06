"""ClicData business intelligence dashboard — handler for clicdata integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.clicdata.com/v1"


@register_node("clicdata.list_dashboards")
async def clicdata_list_dashboards(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List dashboards.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/dashboards", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("clicdata.list_dashboards")
    return {"data": data}

@register_node("clicdata.get_dashboard")
async def clicdata_get_dashboard(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get dashboard details.

    config/input_data:
      api_key — API key or token (required)
      dashboard_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    dashboard_id = merged.get("dashboard_id") or ""
    if not dashboard_id:
        raise ValueError("dashboard_id required for clicdata.get_dashboard")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/dashboards/{dashboard_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("clicdata.get_dashboard")
    return {"data": data}

@register_node("clicdata.list_data_sources")
async def clicdata_list_data_sources(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List data sources.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/datasources", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("clicdata.list_data_sources")
    return {"data": data}
