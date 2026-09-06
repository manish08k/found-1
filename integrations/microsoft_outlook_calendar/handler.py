"""Microsoft Outlook Calendar integration — calendar events via Microsoft Graph API."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _graph_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


@register_node("outlook_calendar.list_events")
async def outlook_calendar_list_events(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List calendar events from Microsoft Outlook Calendar.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      top          — maximum number of events to return (optional, default 25)
      filter       — OData filter expression (optional)
      order_by     — OData orderby expression (optional, default "start/dateTime")
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")

    params: dict = {}
    if merged.get("top"):
        params["$top"] = merged["top"]
    if merged.get("filter"):
        params["$filter"] = merged["filter"]
    params["$orderby"] = merged.get("order_by", "start/dateTime")

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.get("/me/calendar/events", headers=_graph_headers(access_token), params=params)
        r.raise_for_status()
        data = r.json()

    events = data.get("value", [])
    log.info("outlook_calendar.list_events", count=len(events))
    return {"events": events, "count": len(events)}


@register_node("outlook_calendar.create_event")
async def outlook_calendar_create_event(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new calendar event in Microsoft Outlook Calendar.

    config/input_data:
      access_token    — Microsoft Graph OAuth2 bearer token (required)
      subject         — event subject/title (required)
      start_datetime  — start date/time in ISO 8601 format (required)
      end_datetime    — end date/time in ISO 8601 format (required)
      timezone        — timezone for start/end, e.g. "UTC" (optional, default "UTC")
      body            — event body/description (optional)
      content_type    — body content type: "Text" or "HTML" (optional, default "Text")
      location        — event location string (optional)
      attendees       — list of attendee email addresses (optional)
      is_online       — whether to create as Teams meeting (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    subject = merged.get("subject")
    start_datetime = merged.get("start_datetime")
    end_datetime = merged.get("end_datetime")
    if not subject:
        raise ValueError("subject is required for outlook_calendar.create_event")
    if not start_datetime:
        raise ValueError("start_datetime is required for outlook_calendar.create_event")
    if not end_datetime:
        raise ValueError("end_datetime is required for outlook_calendar.create_event")

    timezone = merged.get("timezone", "UTC")
    payload: dict = {
        "subject": subject,
        "start": {"dateTime": start_datetime, "timeZone": timezone},
        "end": {"dateTime": end_datetime, "timeZone": timezone},
    }
    if merged.get("body") is not None:
        payload["body"] = {
            "contentType": merged.get("content_type", "Text"),
            "content": merged["body"],
        }
    if merged.get("location"):
        payload["location"] = {"displayName": merged["location"]}
    if merged.get("attendees"):
        payload["attendees"] = [
            {"emailAddress": {"address": e}, "type": "required"}
            for e in merged["attendees"]
        ]
    if merged.get("is_online"):
        payload["isOnlineMeeting"] = True
        payload["onlineMeetingProvider"] = "teamsForBusiness"

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.post("/me/calendar/events", headers=_graph_headers(access_token), json=payload)
        r.raise_for_status()
        event = r.json()

    log.info("outlook_calendar.create_event", event_id=event.get("id"), subject=subject)
    return {"event": event, "event_id": event.get("id")}


@register_node("outlook_calendar.update_event")
async def outlook_calendar_update_event(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update an existing calendar event in Microsoft Outlook Calendar.

    config/input_data:
      access_token   — Microsoft Graph OAuth2 bearer token (required)
      event_id       — event ID to update (required)
      subject        — new event subject (optional)
      start_datetime — new start date/time in ISO 8601 format (optional)
      end_datetime   — new end date/time in ISO 8601 format (optional)
      timezone       — timezone for start/end, e.g. "UTC" (optional)
      body           — new event body/description (optional)
      location       — new event location string (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    event_id = merged.get("event_id")
    if not event_id:
        raise ValueError("event_id is required for outlook_calendar.update_event")

    payload: dict = {}
    if merged.get("subject"):
        payload["subject"] = merged["subject"]
    timezone = merged.get("timezone", "UTC")
    if merged.get("start_datetime"):
        payload["start"] = {"dateTime": merged["start_datetime"], "timeZone": timezone}
    if merged.get("end_datetime"):
        payload["end"] = {"dateTime": merged["end_datetime"], "timeZone": timezone}
    if merged.get("body") is not None:
        payload["body"] = {
            "contentType": merged.get("content_type", "Text"),
            "content": merged["body"],
        }
    if merged.get("location"):
        payload["location"] = {"displayName": merged["location"]}

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.patch(f"/me/calendar/events/{event_id}", headers=_graph_headers(access_token), json=payload)
        r.raise_for_status()
        event = r.json()

    log.info("outlook_calendar.update_event", event_id=event_id)
    return {"event": event, "event_id": event_id}


@register_node("outlook_calendar.delete_event")
async def outlook_calendar_delete_event(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete a calendar event from Microsoft Outlook Calendar.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      event_id     — event ID to delete (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    event_id = merged.get("event_id")
    if not event_id:
        raise ValueError("event_id is required for outlook_calendar.delete_event")

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.delete(f"/me/calendar/events/{event_id}", headers=_graph_headers(access_token))
        r.raise_for_status()

    log.info("outlook_calendar.delete_event", event_id=event_id)
    return {"deleted": True, "event_id": event_id}


@register_node("outlook_calendar.get_event")
async def outlook_calendar_get_event(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a specific calendar event from Microsoft Outlook Calendar.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      event_id     — event ID to retrieve (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    event_id = merged.get("event_id")
    if not event_id:
        raise ValueError("event_id is required for outlook_calendar.get_event")

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.get(f"/me/calendar/events/{event_id}", headers=_graph_headers(access_token))
        r.raise_for_status()
        event = r.json()

    log.info("outlook_calendar.get_event", event_id=event_id, subject=event.get("subject"))
    return {"event": event, "event_id": event_id}
