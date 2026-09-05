"""Drift live chat integration — contacts and conversations via the Drift API."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

DRIFT_BASE = "https://driftapi.com"


def _headers(config: dict) -> dict:
    token = config.get("access_token") or ""
    if not token:
        raise ValueError("drift nodes require 'access_token' in config")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


@register_node("drift.get_contacts")
async def drift_get_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Retrieve a list of Drift contacts (up to 50).

    config:
      access_token — Drift OAuth access token
    """
    merged = {**config, **input_data}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{DRIFT_BASE}/contacts", params={"limit": 50}, headers=_headers(merged))
        r.raise_for_status()
        data = r.json()
    contacts = data.get("data", [])
    log.info("drift.get_contacts", count=len(contacts))
    return {"contacts": contacts, "count": len(contacts)}


@register_node("drift.get_contact")
async def drift_get_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a specific Drift contact by ID.

    config:
      access_token — Drift OAuth access token
      contact_id   — numeric ID of the contact
    """
    merged = {**config, **input_data}
    contact_id = merged.get("contact_id")
    if not contact_id:
        raise ValueError("drift.get_contact requires 'contact_id'")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{DRIFT_BASE}/contacts/{contact_id}", headers=_headers(merged))
        r.raise_for_status()
        data = r.json()
    contact = data.get("data", data)
    log.info("drift.get_contact", contact_id=contact_id)
    return {"contact": contact}


@register_node("drift.create_contact")
async def drift_create_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new Drift contact.

    config:
      access_token — Drift OAuth access token
      email        — contact email address
      name         — optional display name
      attributes   — optional dict of additional contact attributes
    """
    merged = {**config, **input_data}
    email = merged.get("email")
    if not email:
        raise ValueError("drift.create_contact requires 'email'")
    attributes: dict = merged.get("attributes") or {}
    attributes["email"] = email
    name = merged.get("name")
    if name:
        attributes["name"] = name
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{DRIFT_BASE}/contacts",
            json={"attributes": attributes},
            headers=_headers(merged),
        )
        r.raise_for_status()
        data = r.json()
    contact = data.get("data", data)
    log.info("drift.create_contact", email=email, contact_id=contact.get("id"))
    return {"contact": contact, "ok": True}


@register_node("drift.update_contact")
async def drift_update_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update attributes on an existing Drift contact.

    config:
      access_token — Drift OAuth access token
      contact_id   — ID of the contact to update
      attributes   — dict of attributes to update
    """
    merged = {**config, **input_data}
    contact_id = merged.get("contact_id")
    attributes: dict = merged.get("attributes") or {}
    if not contact_id:
        raise ValueError("drift.update_contact requires 'contact_id'")
    if not attributes:
        raise ValueError("drift.update_contact requires 'attributes' dict")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.patch(
            f"{DRIFT_BASE}/contacts/{contact_id}",
            json={"attributes": attributes},
            headers=_headers(merged),
        )
        r.raise_for_status()
        data = r.json()
    contact = data.get("data", data)
    log.info("drift.update_contact", contact_id=contact_id)
    return {"contact": contact, "ok": True}


@register_node("drift.list_conversations")
async def drift_list_conversations(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List open Drift conversations (up to 50).

    config:
      access_token — Drift OAuth access token
    """
    merged = {**config, **input_data}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{DRIFT_BASE}/conversations",
            params={"status": "open", "limit": 50},
            headers=_headers(merged),
        )
        r.raise_for_status()
        data = r.json()
    conversations = data.get("data", [])
    log.info("drift.list_conversations", count=len(conversations))
    return {"conversations": conversations, "count": len(conversations)}


@register_node("drift.get_conversation")
async def drift_get_conversation(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a specific Drift conversation by ID.

    config:
      access_token    — Drift OAuth access token
      conversation_id — ID of the conversation
    """
    merged = {**config, **input_data}
    conversation_id = merged.get("conversation_id")
    if not conversation_id:
        raise ValueError("drift.get_conversation requires 'conversation_id'")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{DRIFT_BASE}/conversations/{conversation_id}", headers=_headers(merged))
        r.raise_for_status()
        data = r.json()
    conversation = data.get("data", data)
    log.info("drift.get_conversation", conversation_id=conversation_id)
    return {"conversation": conversation}


@register_node("drift.send_message")
async def drift_send_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a message in an existing Drift conversation.

    config:
      access_token    — Drift OAuth access token
      conversation_id — ID of the conversation to post to
      body            — text body of the message
    """
    merged = {**config, **input_data}
    conversation_id = merged.get("conversation_id")
    body = merged.get("body") or merged.get("message", "")
    if not conversation_id:
        raise ValueError("drift.send_message requires 'conversation_id'")
    if not body:
        raise ValueError("drift.send_message requires 'body' text")
    payload = {"type": "chat", "body": body}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{DRIFT_BASE}/conversations/{conversation_id}/messages",
            json=payload,
            headers=_headers(merged),
        )
        r.raise_for_status()
        data = r.json()
    message = data.get("data", data)
    log.info("drift.send_message", conversation_id=conversation_id, message_id=message.get("id"))
    return {"message": message, "ok": True}
