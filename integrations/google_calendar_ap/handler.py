"""Google Calendar (Activepieces integration) — handler for google_calendar_ap integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://www.googleapis.com/calendar/v3"


@register_node("google_calendar_ap.list_events")
async def google_calendar_ap_list_events(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List calendar events.

    config/input_data:
      api_key — API key or token (required)
      calendar_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    calendar_id = merged.get("calendar_id") or ""
    if not calendar_id:
        raise ValueError("calendar_id required for google_calendar_ap.list_events")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/calendars/{calendar_id}/events", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("google_calendar_ap.list_events")
    return {"data": data}

@register_node("google_calendar_ap.create_event")
async def google_calendar_ap_create_event(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a calendar event.

    config/input_data:
      api_key — API key or token (required)
      calendar_id — (required)
      summary — (required)
      start — (required)
      end — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    calendar_id = merged.get("calendar_id") or ""
    summary = merged.get("summary") or ""
    start = merged.get("start") or ""
    end = merged.get("end") or ""
    if not calendar_id or not summary or not start or not end:
        raise ValueError("calendar_id, summary, start, end required for google_calendar_ap.create_event")
    payload = {"summary": summary, "start": start}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/calendars/{calendar_id}/events", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("google_calendar_ap.create_event")
    return {"data": data}

@register_node("google_calendar_ap.get_event")
async def google_calendar_ap_get_event(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get an event.

    config/input_data:
      api_key — API key or token (required)
      calendar_id — (required)
      event_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    calendar_id = merged.get("calendar_id") or ""
    event_id = merged.get("event_id") or ""
    if not calendar_id or not event_id:
        raise ValueError("calendar_id, event_id required for google_calendar_ap.get_event")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/calendars/{calendar_id}/events/{event_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("google_calendar_ap.get_event")
    return {"data": data}

@register_node("google_calendar_ap.delete_event")
async def google_calendar_ap_delete_event(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete an event.

    config/input_data:
      api_key — API key or token (required)
      calendar_id — (required)
      event_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    calendar_id = merged.get("calendar_id") or ""
    event_id = merged.get("event_id") or ""
    if not calendar_id or not event_id:
        raise ValueError("calendar_id, event_id required for google_calendar_ap.delete_event")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.delete(f"{BASE_URL}/calendars/{calendar_id}/events/{event_id}", headers=headers)
        r.raise_for_status()
    log.info("google_calendar_ap.delete_event")
    return {"ok": True}
