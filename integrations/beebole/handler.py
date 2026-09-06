"""Beebole time tracking and reporting — handler for beebole integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://beebole-apps.com/api/v2"


@register_node("beebole.list_time_entries")
async def beebole_list_time_entries(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List time entries.

    config/input_data:
      api_key — API key or token (required)
      service — (required)
    """
    merged = {**config, **input_data}
    username = merged.get("username") or merged.get("api_key") or ""
    password = merged.get("password") or merged.get("api_token") or ""
    import base64
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}
    service = merged.get("service") or ""
    if not service:
        raise ValueError("service required for beebole.list_time_entries")
    payload = {"service": service}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("beebole.list_time_entries")
    return {"data": data}

@register_node("beebole.create_time_entry")
async def beebole_create_time_entry(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a time entry.

    config/input_data:
      api_key — API key or token (required)
      service — (required)
      date — (required)
      hours — (required)
    """
    merged = {**config, **input_data}
    username = merged.get("username") or merged.get("api_key") or ""
    password = merged.get("password") or merged.get("api_token") or ""
    import base64
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}
    service = merged.get("service") or ""
    date = merged.get("date") or ""
    hours = merged.get("hours") or ""
    if not service or not date or not hours:
        raise ValueError("service, date, hours required for beebole.create_time_entry")
    payload = {"service": service, "date": date, "hours": hours}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("beebole.create_time_entry")
    return {"data": data}
