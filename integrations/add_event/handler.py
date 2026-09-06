"""AddEvent calendar event sharing — handler for add_event integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://www.addevent.com/api/v1"


@register_node("add_event.create_event")
async def add_event_create_event(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a calendar event.

    config/input_data:
      api_key — API key or token (required)
      calendar_id — (required)
      title — (required)
      start — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Content-Type": "application/json"}
    # Auth passed as query param: token
    calendar_id = merged.get("calendar_id") or ""
    title = merged.get("title") or ""
    start = merged.get("start") or ""
    if not calendar_id or not title or not start:
        raise ValueError("calendar_id, title, start required for add_event.create_event")
    payload = {"calendar_id": calendar_id, "title": title, "start": start}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/me/calendars/events/create/", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("add_event.create_event")
    return {"data": data}

@register_node("add_event.list_calendars")
async def add_event_list_calendars(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all calendars.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Content-Type": "application/json"}
    # Auth passed as query param: token
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/me/calendars/list/", headers=headers, params={"token": api_key})
        r.raise_for_status()
        data = r.json()
    log.info("add_event.list_calendars")
    return {"data": data}

@register_node("add_event.delete_event")
async def add_event_delete_event(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete an event.

    config/input_data:
      api_key — API key or token (required)
      event_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Content-Type": "application/json"}
    # Auth passed as query param: token
    event_id = merged.get("event_id") or ""
    if not event_id:
        raise ValueError("event_id required for add_event.delete_event")
    payload = {"event_id": event_id}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/me/calendars/events/delete/", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("add_event.delete_event")
    return {"data": data}
