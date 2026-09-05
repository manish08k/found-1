"""
AgileCRM contact and tag management integration.

Provides contact lookup, creation, updates, and tag management
via the AgileCRM REST API.

Credential fields:
  - domain  : AgileCRM subdomain (e.g. 'mycompany' for mycompany.agilecrm.com)
  - email   : Account email address used for Basic auth
  - api_key : AgileCRM REST API key

Auth: HTTP Basic (email : api_key).
"""
import base64
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    domain = creds.get("domain", "").strip().rstrip("/")
    email = creds.get("email")
    api_key = creds.get("api_key")

    if not domain:
        raise ValueError("AgileCRM credential missing 'domain'")
    if not email:
        raise ValueError("AgileCRM credential missing 'email'")
    if not api_key:
        raise ValueError("AgileCRM credential missing 'api_key'")

    base_url = f"https://{domain}.agilecrm.com/dev/api"
    token = base64.b64encode(f"{email}:{api_key}".encode()).decode()
    return httpx.AsyncClient(
        base_url=base_url,
        headers={
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
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
        raise ValueError(f"AgileCRM API error {r.status_code}: {detail}")


def _build_contact_payload(config: dict, input_data: dict) -> dict:
    """Build a contact payload matching AgileCRM's nested properties structure."""
    properties = []

    field_map = {
        "first_name": ("SYSTEM", "first_name"),
        "last_name": ("SYSTEM", "last_name"),
        "email": ("SYSTEM", "email"),
        "phone": ("SYSTEM", "phone"),
        "company": ("SYSTEM", "company"),
        "website": ("SYSTEM", "website"),
        "title": ("SYSTEM", "title"),
    }

    for field_key, (prop_type, prop_name) in field_map.items():
        val = config.get(field_key) or input_data.get(field_key)
        if val:
            properties.append({
                "type": prop_type,
                "name": prop_name,
                "value": str(val),
            })

    payload: dict = {}
    if properties:
        payload["properties"] = properties

    lead_score = config.get("lead_score") or input_data.get("lead_score")
    if lead_score is not None:
        payload["lead_score"] = int(lead_score)

    star_value = config.get("star_value") or input_data.get("star_value")
    if star_value is not None:
        payload["star_value"] = int(star_value)

    return payload


@register_node("agilecrm.get_contact")
async def agile_get_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve a contact by ID or search by email."""
    contact_id = config.get("contact_id") or input_data.get("contact_id")
    email = config.get("email") or input_data.get("email")

    async with await _client(credential_id, db) as client:
        if contact_id:
            r = await client.get(f"/contacts/{contact_id}")
            _raise_for_status(r)
            contact = r.json()
        elif email:
            r = await client.get("/contacts/search/email", params={"email": email})
            _raise_for_status(r)
            contact = r.json()
        else:
            raise ValueError("agilecrm.get_contact requires 'contact_id' or 'email'")

    return {"contact": contact, "contact_id": contact.get("id") if isinstance(contact, dict) else None}


@register_node("agilecrm.create_contact")
async def agile_create_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new contact in AgileCRM."""
    payload = _build_contact_payload(config, input_data)

    if not payload.get("properties"):
        raise ValueError("agilecrm.create_contact requires at least one contact field (e.g. 'email', 'first_name')")

    tags_raw = config.get("tags") or input_data.get("tags", "")
    if tags_raw:
        if isinstance(tags_raw, str):
            payload["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]
        elif isinstance(tags_raw, list):
            payload["tags"] = tags_raw

    async with await _client(credential_id, db) as client:
        r = await client.post("/contacts", json=payload)
        _raise_for_status(r)
        contact = r.json()

    contact_id = contact.get("id")
    log.info("agilecrm.create_contact", contact_id=contact_id)
    return {"contact": contact, "contact_id": contact_id}


@register_node("agilecrm.update_contact")
async def agile_update_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Update fields on an existing AgileCRM contact."""
    contact_id = config.get("contact_id") or input_data.get("contact_id")
    if not contact_id:
        raise ValueError("agilecrm.update_contact requires 'contact_id'")

    payload = _build_contact_payload(config, input_data)
    payload["id"] = int(contact_id)

    async with await _client(credential_id, db) as client:
        r = await client.put("/contacts/edit-properties", json=payload)
        _raise_for_status(r)
        contact = r.json()

    log.info("agilecrm.update_contact", contact_id=contact_id)
    return {"contact": contact, "contact_id": contact_id, "updated": True}


@register_node("agilecrm.add_tag")
async def agile_add_tag(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Add one or more tags to a contact in AgileCRM."""
    contact_id = config.get("contact_id") or input_data.get("contact_id")
    tags_raw = config.get("tags") or input_data.get("tags")

    if not contact_id:
        raise ValueError("agilecrm.add_tag requires 'contact_id'")
    if not tags_raw:
        raise ValueError("agilecrm.add_tag requires 'tags' (string or list)")

    if isinstance(tags_raw, str):
        tag_list = [t.strip() for t in tags_raw.split(",") if t.strip()]
    elif isinstance(tags_raw, list):
        tag_list = [str(t).strip() for t in tags_raw if t]
    else:
        tag_list = [str(tags_raw)]

    payload = {"id": str(contact_id), "tags": tag_list}

    async with await _client(credential_id, db) as client:
        r = await client.post("/contacts/edit/tags", json=payload)
        _raise_for_status(r)
        result = r.json()

    log.info("agilecrm.add_tag", contact_id=contact_id, tags=tag_list)
    return {"contact": result, "contact_id": contact_id, "tags_added": tag_list}


@register_node("agilecrm.list_contacts")
async def agile_list_contacts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List contacts from AgileCRM with pagination support."""
    cursor = config.get("cursor") or input_data.get("cursor")
    page_size = int(config.get("page_size") or input_data.get("page_size", 25))

    params: dict = {"page_size": page_size}
    if cursor:
        params["cursor"] = cursor

    async with await _client(credential_id, db) as client:
        r = await client.get("/contacts", params=params)
        _raise_for_status(r)
        contacts = r.json()

    return {
        "contacts": contacts if isinstance(contacts, list) else [],
        "count": len(contacts) if isinstance(contacts, list) else 0,
    }
