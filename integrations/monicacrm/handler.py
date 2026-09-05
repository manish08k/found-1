"""
Monica personal CRM integration.

Provides contact management, note creation, and activity listing via the
Monica API.

Credential fields:
  - host    : Monica instance hostname, e.g. app.monicahq.com or self-hosted domain
  - api_key : Monica personal access token

Auth: Bearer token in Authorization header.
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    host = creds.get("host", "").strip().rstrip("/")
    api_key = creds.get("api_key")
    if not host:
        raise ValueError("Monica CRM credential missing 'host'")
    if not api_key:
        raise ValueError("Monica CRM credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=f"https://{host}/api/",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Monica CRM API error {r.status_code}: {detail}")


@register_node("monicacrm.list_contacts")
async def monica_list_contacts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all contacts in Monica CRM."""
    page = int(config.get("page") or input_data.get("page", 1))
    limit = int(config.get("limit") or input_data.get("limit", 10))
    query = config.get("query") or input_data.get("query")

    params: dict = {"page": page, "limit": limit}
    if query:
        params["query"] = query

    log.info("monicacrm.list_contacts", page=page, limit=limit)
    async with await _client(credential_id, db) as client:
        r = await client.get("contacts", params=params)
        _raise_for_status(r)
        data = r.json()

    return {
        "contacts": data.get("data", []),
        "meta": data.get("meta", {}),
        "links": data.get("links", {}),
    }


@register_node("monicacrm.create_contact")
async def monica_create_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new contact in Monica CRM."""
    first_name = config.get("first_name") or input_data.get("first_name")
    if not first_name:
        raise ValueError("monicacrm.create_contact requires 'first_name'")

    last_name = config.get("last_name") or input_data.get("last_name", "")
    nickname = config.get("nickname") or input_data.get("nickname", "")
    gender_type = config.get("gender_type") or input_data.get("gender_type", "O")
    is_partial = bool(config.get("is_partial") or input_data.get("is_partial", False))

    payload: dict = {
        "first_name": first_name,
        "gender_type": gender_type,
        "is_partial": is_partial,
    }
    if last_name:
        payload["last_name"] = last_name
    if nickname:
        payload["nickname"] = nickname

    log.info("monicacrm.create_contact", first_name=first_name, last_name=last_name)
    async with await _client(credential_id, db) as client:
        r = await client.post("contacts", json=payload)
        _raise_for_status(r)
        data = r.json()

    contact = data.get("data", data)
    return {"contact": contact, "contact_id": contact.get("id")}


@register_node("monicacrm.create_note")
async def monica_create_note(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a note for a contact in Monica CRM."""
    contact_id = config.get("contact_id") or input_data.get("contact_id")
    body = config.get("body") or input_data.get("body") or config.get("note") or input_data.get("note")

    if not contact_id:
        raise ValueError("monicacrm.create_note requires 'contact_id'")
    if not body:
        raise ValueError("monicacrm.create_note requires 'body'")

    is_favorited = bool(config.get("is_favorited") or input_data.get("is_favorited", False))

    payload = {
        "contact_id": int(contact_id),
        "body": body,
        "is_favorited": is_favorited,
    }

    log.info("monicacrm.create_note", contact_id=contact_id)
    async with await _client(credential_id, db) as client:
        r = await client.post("notes", json=payload)
        _raise_for_status(r)
        data = r.json()

    note = data.get("data", data)
    return {"note": note, "note_id": note.get("id")}


@register_node("monicacrm.list_activities")
async def monica_list_activities(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List activities from Monica CRM, optionally filtered by contact."""
    contact_id = config.get("contact_id") or input_data.get("contact_id")
    page = int(config.get("page") or input_data.get("page", 1))
    limit = int(config.get("limit") or input_data.get("limit", 10))

    params: dict = {"page": page, "limit": limit}

    log.info("monicacrm.list_activities", contact_id=contact_id, page=page)
    async with await _client(credential_id, db) as client:
        if contact_id:
            r = await client.get(f"contacts/{contact_id}/activities", params=params)
        else:
            r = await client.get("activities", params=params)
        _raise_for_status(r)
        data = r.json()

    return {
        "activities": data.get("data", []),
        "meta": data.get("meta", {}),
        "links": data.get("links", {}),
    }
