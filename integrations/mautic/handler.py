"""
Mautic marketing automation integration.

Provides contact management, campaign operations, and email sending
via the Mautic REST API.

Credential fields:
  - base_url : Mautic instance base URL, e.g. https://mautic.example.com
  - username : Mautic username
  - password : Mautic password

Auth: HTTP Basic authentication.
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    base_url = creds.get("base_url", "").rstrip("/")
    username = creds.get("username")
    password = creds.get("password")
    if not base_url:
        raise ValueError("Mautic credential missing 'base_url'")
    if not username or not password:
        raise ValueError("Mautic credential missing 'username' or 'password'")
    return httpx.AsyncClient(
        base_url=f"{base_url}/api",
        auth=(username, password),
        headers={"Content-Type": "application/json"},
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Mautic API error {r.status_code}: {detail}")


@register_node("mautic.create_contact")
async def mautic_create_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new contact in Mautic."""
    email = config.get("email") or input_data.get("email")
    first_name = config.get("firstname") or input_data.get("firstname") or config.get("first_name") or input_data.get("first_name", "")
    last_name = config.get("lastname") or input_data.get("lastname") or config.get("last_name") or input_data.get("last_name", "")
    company = config.get("company") or input_data.get("company", "")
    phone = config.get("phone") or input_data.get("phone", "")

    if not email:
        raise ValueError("mautic.create_contact requires 'email'")

    payload: dict = {"email": email}
    if first_name:
        payload["firstname"] = first_name
    if last_name:
        payload["lastname"] = last_name
    if company:
        payload["company"] = company
    if phone:
        payload["phone"] = phone

    log.info("mautic.create_contact", email=email)
    async with await _client(credential_id, db) as client:
        r = await client.post("/contacts/new", json=payload)
        _raise_for_status(r)
        data = r.json()

    contact = data.get("contact", {})
    return {"contact": contact, "contact_id": contact.get("id")}


@register_node("mautic.list_contacts")
async def mautic_list_contacts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List contacts in Mautic."""
    limit = int(config.get("limit") or input_data.get("limit", 30))
    start = int(config.get("start") or input_data.get("start", 0))
    search = config.get("search") or input_data.get("search", "")

    params: dict = {"limit": limit, "start": start}
    if search:
        params["search"] = search

    log.info("mautic.list_contacts", limit=limit, start=start)
    async with await _client(credential_id, db) as client:
        r = await client.get("/contacts", params=params)
        _raise_for_status(r)
        data = r.json()

    contacts_raw = data.get("contacts", {})
    # Mautic returns contacts as an object keyed by ID; normalise to list
    contacts_list = list(contacts_raw.values()) if isinstance(contacts_raw, dict) else contacts_raw

    return {
        "contacts": contacts_list,
        "total": data.get("total", len(contacts_list)),
    }


@register_node("mautic.add_to_campaign")
async def mautic_add_to_campaign(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Add a contact to a Mautic campaign."""
    campaign_id = config.get("campaign_id") or input_data.get("campaign_id")
    contact_id = config.get("contact_id") or input_data.get("contact_id")

    if not campaign_id:
        raise ValueError("mautic.add_to_campaign requires 'campaign_id'")
    if not contact_id:
        raise ValueError("mautic.add_to_campaign requires 'contact_id'")

    log.info("mautic.add_to_campaign", campaign_id=campaign_id, contact_id=contact_id)
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/campaigns/{campaign_id}/contact/{contact_id}/add")
        _raise_for_status(r)
        data = r.json()

    return {"success": data.get("success", True), "campaign_id": campaign_id, "contact_id": contact_id}


@register_node("mautic.send_email")
async def mautic_send_email(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Send a Mautic email to a specific contact."""
    email_id = config.get("email_id") or input_data.get("email_id")
    contact_id = config.get("contact_id") or input_data.get("contact_id")
    tokens = config.get("tokens") or input_data.get("tokens", {})

    if not email_id:
        raise ValueError("mautic.send_email requires 'email_id'")
    if not contact_id:
        raise ValueError("mautic.send_email requires 'contact_id'")

    payload: dict = {}
    if tokens and isinstance(tokens, dict):
        payload["tokens"] = tokens

    log.info("mautic.send_email", email_id=email_id, contact_id=contact_id)
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/emails/{email_id}/contact/{contact_id}/send", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"success": data.get("success", True), "email_id": email_id, "contact_id": contact_id}
