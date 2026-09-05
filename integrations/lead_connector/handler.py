"""Lead Connector (GoHighLevel) CRM integration — contacts and opportunities."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

LEAD_CONNECTOR_BASE = "https://rest.gohighlevel.com/v1"


@register_node("lead_connector.list_contacts")
async def lead_connector_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts from Lead Connector (GHL).

    config/input_data:
      api_key     — Lead Connector API key (required)
      location_id — location/sub-account ID (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    location_id = merged.get("location_id") or ""

    if not location_id:
        raise ValueError("location_id is required for lead_connector.list_contacts")

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{LEAD_CONNECTOR_BASE}/contacts/"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params={"locationId": location_id})
        r.raise_for_status()
        data = r.json()

    contacts = data.get("contacts", data)
    log.info("lead_connector.list_contacts", location_id=location_id, count=len(contacts) if isinstance(contacts, list) else None)
    return {"contacts": contacts}


@register_node("lead_connector.create_contact")
async def lead_connector_create_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a contact in Lead Connector (GHL).

    config/input_data:
      api_key     — Lead Connector API key (required)
      location_id — location/sub-account ID (required)
      first_name  — first name
      last_name   — last name
      email       — email address
      phone       — phone number
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    location_id = merged.get("location_id") or ""
    fn = merged.get("first_name") or ""
    ln = merged.get("last_name") or ""
    email = merged.get("email") or ""
    phone = merged.get("phone") or ""

    if not location_id:
        raise ValueError("location_id is required for lead_connector.create_contact")

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{LEAD_CONNECTOR_BASE}/contacts/"
    payload: dict = {"locationId": location_id}
    if fn:
        payload["firstName"] = fn
    if ln:
        payload["lastName"] = ln
    if email:
        payload["email"] = email
    if phone:
        payload["phone"] = phone

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    contact = data.get("contact", data)
    log.info("lead_connector.create_contact", email=email, id=contact.get("id") if isinstance(contact, dict) else None)
    return {"contact": contact}


@register_node("lead_connector.get_contact")
async def lead_connector_get_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single Lead Connector contact by ID.

    config/input_data:
      api_key — Lead Connector API key (required)
      id      — contact ID (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    contact_id = merged.get("id") or merged.get("contact_id") or ""

    if not contact_id:
        raise ValueError("id is required for lead_connector.get_contact")

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{LEAD_CONNECTOR_BASE}/contacts/{contact_id}"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()

    contact = data.get("contact", data)
    log.info("lead_connector.get_contact", id=contact_id)
    return {"contact": contact}


@register_node("lead_connector.list_opportunities")
async def lead_connector_list_opportunities(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List opportunities from Lead Connector (GHL).

    config/input_data:
      api_key     — Lead Connector API key (required)
      location_id — location/sub-account ID (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    location_id = merged.get("location_id") or ""

    if not location_id:
        raise ValueError("location_id is required for lead_connector.list_opportunities")

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{LEAD_CONNECTOR_BASE}/opportunities/search"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params={"location_id": location_id})
        r.raise_for_status()
        data = r.json()

    opportunities = data.get("opportunities", data)
    log.info("lead_connector.list_opportunities", location_id=location_id, count=len(opportunities) if isinstance(opportunities, list) else None)
    return {"opportunities": opportunities}
