"""Plunk integration — transactional email and event tracking via Plunk API v1."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

PLUNK_BASE = "https://api.useplunk.com/v1"


def _headers(config: dict, input_data: dict) -> dict:
    merged = {**config, **input_data}
    return {"Authorization": f"Bearer {merged.get('api_key', '')}"}


@register_node("plunk.track_event")
async def track_event(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Track an event for a contact in Plunk.

    config/input_data:
      api_key    — Plunk API key (required)
      event_name — Name of the event (required)
      email      — Contact email address (required)
      data       — Additional event data dict (optional)
    """
    merged = {**config, **input_data}
    event_name = merged.get("event_name", "") or merged.get("event", "")
    email = merged.get("email", "")
    if not event_name or not email:
        raise ValueError("event_name and email are required for plunk.track_event")
    headers = _headers(config, input_data)
    payload = {"event": event_name, "email": email, "data": merged.get("data", {})}
    async with httpx.AsyncClient(base_url=PLUNK_BASE, timeout=30) as client:
        r = await client.post("/track", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("plunk.track_event", email=email, event_name=event_name)
    return {"result": data, "email": email, "event_name": event_name}


@register_node("plunk.send_transactional")
async def send_transactional(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a transactional email via Plunk.

    config/input_data:
      api_key   — Plunk API key (required)
      to        — Recipient email address (required)
      subject   — Email subject (required)
      html_body — HTML body content (required)
    """
    merged = {**config, **input_data}
    to = merged.get("to", "") or merged.get("email", "")
    subject = merged.get("subject", "")
    html_body = merged.get("html_body", "") or merged.get("body", "")
    if not to or not subject:
        raise ValueError("to and subject are required for plunk.send_transactional")
    headers = _headers(config, input_data)
    payload = {"to": to, "subject": subject, "body": html_body}
    async with httpx.AsyncClient(base_url=PLUNK_BASE, timeout=30) as client:
        r = await client.post("/send", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("plunk.send_transactional", to=to, subject=subject)
    return {"result": data, "to": to, "subject": subject}
