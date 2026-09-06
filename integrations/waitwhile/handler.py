"""Waitwhile queue and waitlist management — handler for waitwhile integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.waitwhile.com/v2"


@register_node("waitwhile.list_locations")
async def waitwhile_list_locations(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List locations.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/locations", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("waitwhile.list_locations")
    return {"data": data}

@register_node("waitwhile.add_guest")
async def waitwhile_add_guest(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Add guest to waitlist.

    config/input_data:
      api_key — API key or token (required)
      location_id — (required)
      name — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    location_id = merged.get("location_id") or ""
    name = merged.get("name") or ""
    if not location_id or not name:
        raise ValueError("location_id, name required for waitwhile.add_guest")
    payload = {"name": name}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/locations/{location_id}/waitlist", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("waitwhile.add_guest")
    return {"data": data}

@register_node("waitwhile.list_waitlist")
async def waitwhile_list_waitlist(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List waitlist entries.

    config/input_data:
      api_key — API key or token (required)
      location_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    location_id = merged.get("location_id") or ""
    if not location_id:
        raise ValueError("location_id required for waitwhile.list_waitlist")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/locations/{location_id}/waitlist", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("waitwhile.list_waitlist")
    return {"data": data}
