"""Respond.io messaging CRM integration — contacts and messages."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

RESPOND_IO_BASE = "https://api.respond.io/v2"


@register_node("respond_io.list_contacts")
async def respond_io_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts from Respond.io.

    config/input_data:
      api_key — Respond.io API key (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{RESPOND_IO_BASE}/contact"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()

    contacts = data.get("data", data)
    log.info("respond_io.list_contacts", count=len(contacts) if isinstance(contacts, list) else None)
    return {"contacts": contacts}


@register_node("respond_io.get_contact")
async def respond_io_get_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single Respond.io contact by ID.

    config/input_data:
      api_key — Respond.io API key (required)
      id      — contact ID (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    contact_id = merged.get("id") or merged.get("contact_id") or ""

    if not contact_id:
        raise ValueError("id is required for respond_io.get_contact")

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{RESPOND_IO_BASE}/contact/{contact_id}"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()

    contact = data.get("data", data)
    log.info("respond_io.get_contact", id=contact_id)
    return {"contact": contact}


@register_node("respond_io.create_contact")
async def respond_io_create_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new contact in Respond.io.

    config/input_data:
      api_key    — Respond.io API key (required)
      phone      — phone number (required)
      first_name — first name
      last_name  — last name
      email      — email address
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    phone = merged.get("phone") or ""
    fn = merged.get("first_name") or ""
    ln = merged.get("last_name") or ""
    email = merged.get("email") or ""

    if not phone:
        raise ValueError("phone is required for respond_io.create_contact")

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{RESPOND_IO_BASE}/contact"
    payload: dict = {"phone": phone}
    if fn:
        payload["firstName"] = fn
    if ln:
        payload["lastName"] = ln
    if email:
        payload["email"] = email

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    contact = data.get("data", data)
    log.info("respond_io.create_contact", phone=phone, email=email)
    return {"contact": contact}


@register_node("respond_io.send_message")
async def respond_io_send_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a message to a contact via Respond.io.

    config/input_data:
      api_key    — Respond.io API key (required)
      id         — contact ID (required)
      channel_id — channel ID to send through (required)
      text       — message text (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    contact_id = merged.get("id") or merged.get("contact_id") or ""
    channel_id = merged.get("channel_id") or ""
    text = merged.get("text") or merged.get("message") or ""

    if not contact_id:
        raise ValueError("id is required for respond_io.send_message")
    if not channel_id:
        raise ValueError("channel_id is required for respond_io.send_message")
    if not text:
        raise ValueError("text is required for respond_io.send_message")

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{RESPOND_IO_BASE}/contact/{contact_id}/sendMessage"
    payload = {
        "channelId": channel_id,
        "message": {"type": "text", "text": text},
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    log.info("respond_io.send_message", contact_id=contact_id, channel_id=channel_id)
    return {"result": data}
