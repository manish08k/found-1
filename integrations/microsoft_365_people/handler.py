"""Microsoft 365 People integration — manage contacts via Microsoft Graph API."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _graph_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


@register_node("microsoft_365_people.get_contact")
async def microsoft_365_people_get_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a specific contact by ID from Microsoft 365.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      contact_id   — contact ID to retrieve (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    contact_id = merged.get("contact_id")
    if not contact_id:
        raise ValueError("contact_id is required for microsoft_365_people.get_contact")

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.get(f"/me/contacts/{contact_id}", headers=_graph_headers(access_token))
        r.raise_for_status()
        contact = r.json()

    log.info("microsoft_365_people.get_contact", contact_id=contact_id)
    return {"contact": contact, "contact_id": contact_id}


@register_node("microsoft_365_people.list_contacts")
async def microsoft_365_people_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts from Microsoft 365.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      top          — maximum number of contacts to return (optional, default 50)
      skip         — number of contacts to skip for pagination (optional)
      filter       — OData filter expression (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")

    params: dict = {}
    if merged.get("top"):
        params["$top"] = merged["top"]
    if merged.get("skip"):
        params["$skip"] = merged["skip"]
    if merged.get("filter"):
        params["$filter"] = merged["filter"]

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.get("/me/contacts", headers=_graph_headers(access_token), params=params)
        r.raise_for_status()
        data = r.json()

    contacts = data.get("value", [])
    log.info("microsoft_365_people.list_contacts", count=len(contacts))
    return {"contacts": contacts, "count": len(contacts)}


@register_node("microsoft_365_people.create_contact")
async def microsoft_365_people_create_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new contact in Microsoft 365.

    config/input_data:
      access_token    — Microsoft Graph OAuth2 bearer token (required)
      given_name      — contact's first name (required)
      surname         — contact's last name (optional)
      email_addresses — list of email address objects (optional)
      business_phones — list of phone number strings (optional)
      job_title       — contact's job title (optional)
      company_name    — contact's company (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    given_name = merged.get("given_name")
    if not given_name:
        raise ValueError("given_name is required for microsoft_365_people.create_contact")

    payload: dict = {"givenName": given_name}
    if merged.get("surname"):
        payload["surname"] = merged["surname"]
    if merged.get("email_addresses"):
        payload["emailAddresses"] = merged["email_addresses"]
    if merged.get("business_phones"):
        payload["businessPhones"] = merged["business_phones"]
    if merged.get("job_title"):
        payload["jobTitle"] = merged["job_title"]
    if merged.get("company_name"):
        payload["companyName"] = merged["company_name"]

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.post("/me/contacts", headers=_graph_headers(access_token), json=payload)
        r.raise_for_status()
        contact = r.json()

    log.info("microsoft_365_people.create_contact", contact_id=contact.get("id"))
    return {"contact": contact, "contact_id": contact.get("id")}


@register_node("microsoft_365_people.update_contact")
async def microsoft_365_people_update_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update an existing contact in Microsoft 365.

    config/input_data:
      access_token    — Microsoft Graph OAuth2 bearer token (required)
      contact_id      — contact ID to update (required)
      given_name      — contact's first name (optional)
      surname         — contact's last name (optional)
      email_addresses — list of email address objects (optional)
      business_phones — list of phone number strings (optional)
      job_title       — contact's job title (optional)
      company_name    — contact's company (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    contact_id = merged.get("contact_id")
    if not contact_id:
        raise ValueError("contact_id is required for microsoft_365_people.update_contact")

    payload: dict = {}
    if merged.get("given_name"):
        payload["givenName"] = merged["given_name"]
    if merged.get("surname"):
        payload["surname"] = merged["surname"]
    if merged.get("email_addresses"):
        payload["emailAddresses"] = merged["email_addresses"]
    if merged.get("business_phones"):
        payload["businessPhones"] = merged["business_phones"]
    if merged.get("job_title"):
        payload["jobTitle"] = merged["job_title"]
    if merged.get("company_name"):
        payload["companyName"] = merged["company_name"]

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.patch(f"/me/contacts/{contact_id}", headers=_graph_headers(access_token), json=payload)
        r.raise_for_status()
        contact = r.json()

    log.info("microsoft_365_people.update_contact", contact_id=contact_id)
    return {"contact": contact, "contact_id": contact_id}


@register_node("microsoft_365_people.delete_contact")
async def microsoft_365_people_delete_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete a contact from Microsoft 365.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      contact_id   — contact ID to delete (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    contact_id = merged.get("contact_id")
    if not contact_id:
        raise ValueError("contact_id is required for microsoft_365_people.delete_contact")

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.delete(f"/me/contacts/{contact_id}", headers=_graph_headers(access_token))
        r.raise_for_status()

    log.info("microsoft_365_people.delete_contact", contact_id=contact_id)
    return {"deleted": True, "contact_id": contact_id}
