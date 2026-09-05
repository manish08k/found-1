"""Loops integration — transactional email via Loops API v1."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

LOOPS_BASE = "https://app.loops.so/api/v1"


def _headers(config: dict, input_data: dict) -> dict:
    merged = {**config, **input_data}
    return {"Authorization": f"Bearer {merged.get('api_key', '')}"}


@register_node("loops.create_contact")
async def create_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new contact in Loops.

    config/input_data:
      api_key    — Loops API key (required)
      email      — Contact email address (required)
      first_name — Contact first name (optional)
      last_name  — Contact last name (optional)
    """
    merged = {**config, **input_data}
    email = merged.get("email", "")
    if not email:
        raise ValueError("email is required for loops.create_contact")
    headers = _headers(config, input_data)
    payload = {
        "email": email,
        "firstName": merged.get("first_name", ""),
        "lastName": merged.get("last_name", ""),
    }
    async with httpx.AsyncClient(base_url=LOOPS_BASE, timeout=30) as client:
        r = await client.post("/contacts/create", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("loops.create_contact", email=email)
    return {"contact": data, "email": email}


@register_node("loops.update_contact")
async def update_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update an existing contact in Loops.

    config/input_data:
      api_key    — Loops API key (required)
      email      — Contact email address (required)
      user_id    — Contact user ID (optional)
      properties — Additional properties dict (optional)
    """
    merged = {**config, **input_data}
    email = merged.get("email", "")
    if not email:
        raise ValueError("email is required for loops.update_contact")
    headers = _headers(config, input_data)
    payload = {"email": email, "userId": merged.get("user_id", "")}
    extra_props = merged.get("properties", {})
    if isinstance(extra_props, dict):
        payload.update(extra_props)
    async with httpx.AsyncClient(base_url=LOOPS_BASE, timeout=30) as client:
        r = await client.put("/contacts/update", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("loops.update_contact", email=email)
    return {"contact": data, "email": email}


@register_node("loops.send_transactional")
async def send_transactional(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a transactional email via Loops.

    config/input_data:
      api_key           — Loops API key (required)
      transactional_id  — Loops transactional email ID (required)
      email             — Recipient email address (required)
      data_variables    — Dict of template variables (optional)
    """
    merged = {**config, **input_data}
    transactional_id = merged.get("transactional_id", "")
    email = merged.get("email", "")
    if not transactional_id or not email:
        raise ValueError("transactional_id and email are required for loops.send_transactional")
    headers = _headers(config, input_data)
    payload = {
        "transactionalId": transactional_id,
        "email": email,
        "dataVariables": merged.get("data_variables", {}),
    }
    async with httpx.AsyncClient(base_url=LOOPS_BASE, timeout=30) as client:
        r = await client.post("/transactional", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("loops.send_transactional", email=email, transactional_id=transactional_id)
    return {"result": data, "email": email, "transactional_id": transactional_id}


@register_node("loops.send_event")
async def send_event(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send an event for a contact in Loops.

    config/input_data:
      api_key     — Loops API key (required)
      email       — Contact email address (required)
      event_name  — Name of the event (required)
    """
    merged = {**config, **input_data}
    email = merged.get("email", "")
    event_name = merged.get("event_name", "")
    if not email or not event_name:
        raise ValueError("email and event_name are required for loops.send_event")
    headers = _headers(config, input_data)
    payload = {"email": email, "eventName": event_name}
    async with httpx.AsyncClient(base_url=LOOPS_BASE, timeout=30) as client:
        r = await client.post("/events/send", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("loops.send_event", email=email, event_name=event_name)
    return {"result": data, "email": email, "event_name": event_name}
