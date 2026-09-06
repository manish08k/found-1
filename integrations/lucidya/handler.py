"""Lucidya social media analytics — handler for lucidya integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.lucidya.com/v2"


@register_node("lucidya.list_monitors")
async def lucidya_list_monitors(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List monitors.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/monitors", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("lucidya.list_monitors")
    return {"data": data}

@register_node("lucidya.get_insights")
async def lucidya_get_insights(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get monitor insights.

    config/input_data:
      api_key — API key or token (required)
      monitor_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    monitor_id = merged.get("monitor_id") or ""
    if not monitor_id:
        raise ValueError("monitor_id required for lucidya.get_insights")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/monitors/{monitor_id}/insights", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("lucidya.get_insights")
    return {"data": data}
