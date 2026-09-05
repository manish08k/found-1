"""
Autopilot marketing automation integration.

Provides contact creation, updates, and list management
via the Autopilot API v1.

Credential fields:
  - api_key : Autopilot API key

Auth: autopilotapikey header.
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://api2.autopilothq.com/v1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Autopilot credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={
            "autopilotapikey": api_key,
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Autopilot API error {r.status_code}: {detail}")


def _build_contact_payload(config: dict, input_data: dict) -> dict:
    """Build the contact dict expected by Autopilot from config + input_data."""
    contact: dict = {}

    field_map = {
        "email": "Email",
        "first_name": "FirstName",
        "last_name": "LastName",
        "phone": "Phone",
        "mobile_phone": "MobilePhone",
        "company": "Company",
        "website": "Website",
        "title": "Title",
        "salutation": "Salutation",
        "linkedin": "LinkedIn",
        "twitter": "Twitter",
        "fax": "Fax",
        "mailing_street": "MailingStreet",
        "mailing_city": "MailingCity",
        "mailing_state": "MailingState",
        "mailing_postal_code": "MailingPostalCode",
        "mailing_country": "MailingCountry",
    }

    for src_key, dst_key in field_map.items():
        val = config.get(src_key) or input_data.get(src_key)
        if val is not None:
            contact[dst_key] = val

    # Custom fields can be passed as a dict under "custom_fields"
    custom = config.get("custom_fields") or input_data.get("custom_fields", {})
    if isinstance(custom, dict):
        for k, v in custom.items():
            contact[k] = v

    return contact


@register_node("autopilot.add_contact")
async def ap_add_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new contact or update an existing one (upsert by email)."""
    contact = _build_contact_payload(config, input_data)

    if not contact.get("Email"):
        raise ValueError("autopilot.add_contact requires 'email'")

    payload = {"contact": contact}

    async with await _client(credential_id, db) as client:
        r = await client.post("/contact", json=payload)
        _raise_for_status(r)
        result = r.json()

    contact_id = result.get("contact_id", "")
    log.info("autopilot.add_contact", contact_id=contact_id, email=contact.get("Email"))
    return {"contact": result, "contact_id": contact_id}


@register_node("autopilot.update_contact")
async def ap_update_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Update fields on an existing Autopilot contact identified by email or contact ID."""
    contact_id = config.get("contact_id") or input_data.get("contact_id")
    contact = _build_contact_payload(config, input_data)

    if not contact_id and not contact.get("Email"):
        raise ValueError("autopilot.update_contact requires 'contact_id' or 'email'")

    payload = {"contact": contact}

    async with await _client(credential_id, db) as client:
        if contact_id:
            r = await client.post(f"/contact/{contact_id}", json=payload)
        else:
            r = await client.post("/contact", json=payload)
        _raise_for_status(r)
        result = r.json()

    log.info("autopilot.update_contact", contact_id=contact_id or contact.get("Email"))
    return {"contact": result, "contact_id": contact_id, "updated": True}


@register_node("autopilot.add_to_list")
async def ap_add_to_list(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Add a contact to an Autopilot list by list ID and contact email or ID."""
    list_id = config.get("list_id") or input_data.get("list_id")
    contact_id = config.get("contact_id") or input_data.get("contact_id")

    if not list_id:
        raise ValueError("autopilot.add_to_list requires 'list_id'")
    if not contact_id:
        raise ValueError("autopilot.add_to_list requires 'contact_id' (contact ID or email)")

    async with await _client(credential_id, db) as client:
        r = await client.post(f"/list/{list_id}/contact/{contact_id}")
        _raise_for_status(r)

    log.info("autopilot.add_to_list", list_id=list_id, contact_id=contact_id)
    return {"added": True, "list_id": list_id, "contact_id": contact_id}


@register_node("autopilot.remove_from_list")
async def ap_remove_from_list(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Remove a contact from an Autopilot list."""
    list_id = config.get("list_id") or input_data.get("list_id")
    contact_id = config.get("contact_id") or input_data.get("contact_id")

    if not list_id:
        raise ValueError("autopilot.remove_from_list requires 'list_id'")
    if not contact_id:
        raise ValueError("autopilot.remove_from_list requires 'contact_id' (contact ID or email)")

    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/list/{list_id}/contact/{contact_id}")
        _raise_for_status(r)

    log.info("autopilot.remove_from_list", list_id=list_id, contact_id=contact_id)
    return {"removed": True, "list_id": list_id, "contact_id": contact_id}


@register_node("autopilot.get_contact")
async def ap_get_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve a contact record by their email address or contact ID."""
    contact_id = config.get("contact_id") or input_data.get("contact_id")
    if not contact_id:
        raise ValueError("autopilot.get_contact requires 'contact_id' (contact ID or email address)")

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/contact/{contact_id}")
        _raise_for_status(r)
        contact = r.json()

    return {"contact": contact, "contact_id": contact_id}


@register_node("autopilot.list_contacts")
async def ap_list_contacts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all contacts, with optional bookmark-based pagination."""
    bookmark = config.get("bookmark") or input_data.get("bookmark")

    params = {}
    if bookmark:
        params["bookmark"] = bookmark

    async with await _client(credential_id, db) as client:
        r = await client.get("/contacts", params=params)
        _raise_for_status(r)
        data = r.json()

    contacts = data.get("contacts", [])
    return {
        "contacts": contacts,
        "count": len(contacts),
        "total_contacts": data.get("total_contacts", len(contacts)),
        "bookmark": data.get("bookmark"),
    }
