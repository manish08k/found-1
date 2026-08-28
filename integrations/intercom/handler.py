"""
Intercom integration — contacts, conversations, messages, events.
Nodes: intercom.create_contact, intercom.get_contact, intercom.search_contacts,
       intercom.send_message, intercom.create_conversation, intercom.add_note,
       intercom.track_event, intercom.tag_contact
"""
import httpx
import structlog
from core.execution_engine import register_node
from core.config import settings

log = structlog.get_logger(__name__)

INTERCOM_API = "https://api.intercom.io"


def _headers(config):
    token = config.get("access_token") or getattr(settings, "INTERCOM_ACCESS_TOKEN", "")
    if not token:
        raise ValueError("intercom nodes require INTERCOM_ACCESS_TOKEN or 'access_token'")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Intercom-Version": "2.10",
    }


@register_node("intercom.create_contact")
async def intercom_create_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    payload = {k: merged.get(k) for k in ("email", "external_id", "name", "phone", "avatar", "role")
               if merged.get(k)}
    payload["role"] = payload.get("role", "user")
    custom_attributes = merged.get("custom_attributes") or {}
    if custom_attributes:
        payload["custom_attributes"] = custom_attributes

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{INTERCOM_API}/contacts", json=payload, headers=_headers(merged))
        r.raise_for_status()
        return {"contact": r.json(), "ok": True}


@register_node("intercom.get_contact")
async def intercom_get_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    contact_id = merged.get("contact_id")
    if not contact_id:
        raise ValueError("intercom.get_contact requires 'contact_id'")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{INTERCOM_API}/contacts/{contact_id}", headers=_headers(merged))
        r.raise_for_status()
        return {"contact": r.json()}


@register_node("intercom.search_contacts")
async def intercom_search_contacts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    email = merged.get("email")
    name = merged.get("name")
    external_id = merged.get("external_id")

    operators = []
    if email:
        operators.append({"field": "email", "operator": "=", "value": email})
    if external_id:
        operators.append({"field": "external_id", "operator": "=", "value": external_id})

    if not operators:
        raise ValueError("intercom.search_contacts requires at least 'email' or 'external_id'")

    query = {"operator": "AND", "value": operators}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{INTERCOM_API}/contacts/search",
            json={"query": query},
            headers=_headers(merged),
        )
        r.raise_for_status()
        data = r.json()

    return {"contacts": data.get("data", []), "total": data.get("total_count", 0)}


@register_node("intercom.send_message")
async def intercom_send_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    contact_id = merged.get("contact_id")
    body = merged.get("body") or merged.get("message", "")
    message_type = merged.get("message_type", "inapp")  # inapp | email
    subject = merged.get("subject", "")

    if not contact_id:
        raise ValueError("intercom.send_message requires 'contact_id'")

    payload = {
        "message_type": message_type,
        "body": body,
        "to": {"type": "contact", "id": contact_id},
    }
    if subject:
        payload["subject"] = subject

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{INTERCOM_API}/messages", json=payload, headers=_headers(merged))
        r.raise_for_status()
        return {"message": r.json(), "ok": True}


@register_node("intercom.track_event")
async def intercom_track_event(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    event_name = merged.get("event_name")
    contact_id = merged.get("contact_id")
    created_at = merged.get("created_at")

    if not event_name or not contact_id:
        raise ValueError("intercom.track_event requires 'event_name' and 'contact_id'")

    payload = {
        "event_name": event_name,
        "contact_id": contact_id,
        "metadata": merged.get("metadata") or {},
    }
    if created_at:
        payload["created_at"] = created_at

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{INTERCOM_API}/events", json=payload, headers=_headers(merged))
        r.raise_for_status()
        return {"ok": True, "event": event_name}


@register_node("intercom.add_note")
async def intercom_add_note(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    contact_id = merged.get("contact_id")
    body = merged.get("body") or merged.get("note", "")

    if not contact_id:
        raise ValueError("intercom.add_note requires 'contact_id'")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{INTERCOM_API}/notes",
            json={"contact_id": contact_id, "body": body},
            headers=_headers(merged),
        )
        r.raise_for_status()
        return {"note": r.json(), "ok": True}
