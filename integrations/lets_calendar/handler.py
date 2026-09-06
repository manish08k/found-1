"""Lets Calendar scheduling platform — handler for lets_calendar integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.lets-calendar.com/v1"


@register_node("lets_calendar.list_events")
async def lets_calendar_list_events(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List events.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/events", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("lets_calendar.list_events")
    return {"data": data}

@register_node("lets_calendar.create_event")
async def lets_calendar_create_event(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create an event.

    config/input_data:
      api_key — API key or token (required)
      title — (required)
      start — (required)
      end — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    title = merged.get("title") or ""
    start = merged.get("start") or ""
    end = merged.get("end") or ""
    if not title or not start or not end:
        raise ValueError("title, start, end required for lets_calendar.create_event")
    payload = {"title": title, "start": start, "end": end}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/events", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("lets_calendar.create_event")
    return {"data": data}

@register_node("lets_calendar.delete_event")
async def lets_calendar_delete_event(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete an event.

    config/input_data:
      api_key — API key or token (required)
      event_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    event_id = merged.get("event_id") or ""
    if not event_id:
        raise ValueError("event_id required for lets_calendar.delete_event")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.delete(f"{BASE_URL}/events/{event_id}", headers=headers)
        r.raise_for_status()
    log.info("lets_calendar.delete_event")
    return {"ok": True}
