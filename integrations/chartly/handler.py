"""Chartly chart generation service — handler for chartly integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.chartly.io/v1"


@register_node("chartly.create_chart")
async def chartly_create_chart(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a chart.

    config/input_data:
      api_key — API key or token (required)
      type — (required)
      data — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    type = merged.get("type") or ""
    data = merged.get("data") or ""
    if not type or not data:
        raise ValueError("type, data required for chartly.create_chart")
    payload = {"type": type, "data": data}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/charts", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("chartly.create_chart")
    return {"data": data}

@register_node("chartly.get_chart")
async def chartly_get_chart(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a chart.

    config/input_data:
      api_key — API key or token (required)
      chart_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    chart_id = merged.get("chart_id") or ""
    if not chart_id:
        raise ValueError("chart_id required for chartly.get_chart")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/charts/{chart_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("chartly.get_chart")
    return {"data": data}
