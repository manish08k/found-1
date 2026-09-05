"""Demio webinar platform integration — events and participant management."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

DEMIO_BASE = "https://my.demio.com/api/v1"


def _headers(config: dict) -> dict:
    api_key = config.get("api_key") or ""
    api_secret = config.get("api_secret") or ""
    if not api_key or not api_secret:
        raise ValueError("demio nodes require 'api_key' and 'api_secret' in config")
    return {
        "Api-Key": api_key,
        "Api-Secret": api_secret,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


@register_node("demio.list_events")
async def demio_list_events(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Demio webinar events.

    config:
      api_key    — Demio API key
      api_secret — Demio API secret
    """
    merged = {**config, **input_data}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{DEMIO_BASE}/event", headers=_headers(merged))
        r.raise_for_status()
        data = r.json()
    events = data if isinstance(data, list) else data.get("events", [])
    log.info("demio.list_events", count=len(events))
    return {"events": events, "count": len(events)}


@register_node("demio.get_event")
async def demio_get_event(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details for a specific Demio event.

    config:
      api_key    — Demio API key
      api_secret — Demio API secret
      event_id   — ID of the event to retrieve
    """
    merged = {**config, **input_data}
    event_id = merged.get("event_id")
    if not event_id:
        raise ValueError("demio.get_event requires 'event_id'")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{DEMIO_BASE}/event/{event_id}", headers=_headers(merged))
        r.raise_for_status()
        data = r.json()
    log.info("demio.get_event", event_id=event_id)
    return {"event": data}


@register_node("demio.register_participant")
async def demio_register_participant(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Register a participant for a Demio event.

    config:
      api_key    — Demio API key
      api_secret — Demio API secret
      event_id   — ID of the event to register for
      name       — participant full name
      email      — participant email address
      fields     — optional dict of additional registration fields
    """
    merged = {**config, **input_data}
    event_id = merged.get("event_id")
    name = merged.get("name")
    email = merged.get("email")
    if not event_id:
        raise ValueError("demio.register_participant requires 'event_id'")
    if not email:
        raise ValueError("demio.register_participant requires 'email'")
    payload: dict = {"name": name or "", "email": email}
    extra_fields = merged.get("fields")
    if extra_fields and isinstance(extra_fields, dict):
        payload.update(extra_fields)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{DEMIO_BASE}/event/{event_id}/register",
            json=payload,
            headers=_headers(merged),
        )
        r.raise_for_status()
        data = r.json()
    log.info("demio.register_participant", event_id=event_id, email=email)
    return {"registration": data, "ok": True}


@register_node("demio.get_participants")
async def demio_get_participants(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get participants registered for a Demio event.

    config:
      api_key    — Demio API key
      api_secret — Demio API secret
      event_id   — ID of the event
    """
    merged = {**config, **input_data}
    event_id = merged.get("event_id")
    if not event_id:
        raise ValueError("demio.get_participants requires 'event_id'")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{DEMIO_BASE}/event/{event_id}/participants",
            headers=_headers(merged),
        )
        r.raise_for_status()
        data = r.json()
    participants = data if isinstance(data, list) else data.get("participants", [])
    log.info("demio.get_participants", event_id=event_id, count=len(participants))
    return {"participants": participants, "count": len(participants)}
