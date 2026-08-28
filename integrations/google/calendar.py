"""Google Calendar — create, list, update, delete events + polling."""
import structlog
from datetime import datetime, timezone
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from core.execution_engine import register_node
from triggers.engine import register_poller
from credentials.encryption import decrypt_credential
from core.config import settings

log = structlog.get_logger(__name__)


async def _cal_service(credential_id: str, db):
    from sqlalchemy import select
    from storage.models import OAuthCredential
    result = await db.execute(select(OAuthCredential).where(OAuthCredential.id == credential_id))
    cred_row = result.scalar_one()
    token_data = decrypt_credential(cred_row.encrypted_token, settings.CREDENTIAL_ENCRYPTION_KEY)
    creds = Credentials(
        token=token_data.get("access_token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


@register_node("calendar.create_event")
async def calendar_create_event(config: dict, input_data: dict, credential_id: str, db) -> dict:
    service = await _cal_service(credential_id, db)
    calendar_id = config.get("calendar_id", "primary")
    summary = config.get("summary") or input_data.get("summary", "New Event")
    start = config.get("start") or input_data.get("start")
    end = config.get("end") or input_data.get("end")
    description = config.get("description") or input_data.get("description", "")
    attendees = config.get("attendees") or input_data.get("attendees", [])
    timezone_ = config.get("timezone", "UTC")
    location = config.get("location") or input_data.get("location", "")

    event_body = {
        "summary": summary,
        "description": description,
        "location": location,
        "start": {"dateTime": start, "timeZone": timezone_},
        "end": {"dateTime": end, "timeZone": timezone_},
        "attendees": [{"email": a} if isinstance(a, str) else a for a in attendees],
    }

    result = service.events().insert(
        calendarId=calendar_id,
        body=event_body,
        sendUpdates="all" if attendees else "none",
    ).execute()
    return {"event_id": result["id"], "html_link": result.get("htmlLink")}


@register_node("calendar.list_events")
async def calendar_list_events(config: dict, input_data: dict, credential_id: str, db) -> dict:
    service = await _cal_service(credential_id, db)
    calendar_id = config.get("calendar_id", "primary")
    time_min = config.get("time_min") or input_data.get("time_min",
                                                          datetime.now(timezone.utc).isoformat())
    time_max = config.get("time_max") or input_data.get("time_max")
    max_results = config.get("max_results", 10)
    query = config.get("query") or input_data.get("query")

    kwargs = {
        "calendarId": calendar_id,
        "timeMin": time_min,
        "maxResults": max_results,
        "singleEvents": True,
        "orderBy": "startTime",
    }
    if time_max:
        kwargs["timeMax"] = time_max
    if query:
        kwargs["q"] = query

    result = service.events().list(**kwargs).execute()
    events = []
    for e in result.get("items", []):
        events.append({
            "id": e["id"],
            "summary": e.get("summary"),
            "start": e.get("start", {}).get("dateTime") or e.get("start", {}).get("date"),
            "end": e.get("end", {}).get("dateTime") or e.get("end", {}).get("date"),
            "location": e.get("location"),
            "description": e.get("description"),
            "html_link": e.get("htmlLink"),
            "attendees": [a.get("email") for a in e.get("attendees", [])],
        })
    return {"events": events}


@register_node("calendar.update_event")
async def calendar_update_event(config: dict, input_data: dict, credential_id: str, db) -> dict:
    service = await _cal_service(credential_id, db)
    calendar_id = config.get("calendar_id", "primary")
    event_id = config.get("event_id") or input_data.get("event_id")

    event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()

    for field in ["summary", "description", "location"]:
        if config.get(field) or input_data.get(field):
            event[field] = config.get(field) or input_data.get(field)

    if config.get("start") or input_data.get("start"):
        event["start"]["dateTime"] = config.get("start") or input_data.get("start")
    if config.get("end") or input_data.get("end"):
        event["end"]["dateTime"] = config.get("end") or input_data.get("end")

    result = service.events().update(
        calendarId=calendar_id, eventId=event_id, body=event
    ).execute()
    return {"event_id": result["id"], "html_link": result.get("htmlLink")}


@register_node("calendar.delete_event")
async def calendar_delete_event(config: dict, input_data: dict, credential_id: str, db) -> dict:
    service = await _cal_service(credential_id, db)
    calendar_id = config.get("calendar_id", "primary")
    event_id = config.get("event_id") or input_data.get("event_id")

    service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
    return {"ok": True, "event_id": event_id}


@register_node("calendar.quick_add")
async def calendar_quick_add(config: dict, input_data: dict, credential_id: str, db) -> dict:
    service = await _cal_service(credential_id, db)
    calendar_id = config.get("calendar_id", "primary")
    text = config.get("text") or input_data.get("text")

    result = service.events().quickAdd(calendarId=calendar_id, text=text).execute()
    return {"event_id": result["id"], "summary": result.get("summary")}


# ─── Polling: new event ───────────────────────────────────────────────────────

_cal_seen: dict[str, set] = {}


@register_poller("calendar", "new_event")
async def poll_calendar_new_event(config: dict, credential_id: str, db) -> list[dict]:
    service = await _cal_service(credential_id, db)
    calendar_id = config.get("calendar_id", "primary")
    key = f"{credential_id}:{calendar_id}"

    if key not in _cal_seen:
        _cal_seen[key] = set()

    try:
        time_min = datetime.now(timezone.utc).isoformat()
        result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            maxResults=20,
            singleEvents=True,
            orderBy="updated",
        ).execute()

        new_items = []
        for e in result.get("items", []):
            if e["id"] not in _cal_seen[key]:
                new_items.append({
                    "id": e["id"],
                    "summary": e.get("summary"),
                    "start": e.get("start", {}).get("dateTime"),
                    "end": e.get("end", {}).get("dateTime"),
                })
                _cal_seen[key].add(e["id"])

        return new_items
    except Exception as e:
        log.error("calendar_poll_error", error=str(e))
        return []
