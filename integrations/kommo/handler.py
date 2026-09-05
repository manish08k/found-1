"""Kommo CRM (formerly amoCRM) integration — leads and contacts."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _kommo_base(subdomain: str) -> str:
    return f"https://{subdomain}.kommo.com/api/v4"


@register_node("kommo.list_leads")
async def kommo_list_leads(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List leads from Kommo CRM.

    config/input_data:
      access_token — OAuth access token (required)
      subdomain    — account subdomain, e.g. 'mycompany' (required)
      limit        — number of leads to return (default 50)
    """
    merged = {**config, **input_data}
    token = merged.get("access_token") or merged.get("api_key") or ""
    subdomain = merged.get("subdomain") or ""
    limit = int(merged.get("limit", 50))

    if not subdomain:
        raise ValueError("subdomain is required for kommo.list_leads")

    headers = {"Authorization": f"Bearer {token}"}
    url = f"{_kommo_base(subdomain)}/leads"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params={"limit": limit})
        r.raise_for_status()
        data = r.json()

    leads = data.get("_embedded", {}).get("leads", data)
    log.info("kommo.list_leads", subdomain=subdomain, count=len(leads) if isinstance(leads, list) else None)
    return {"leads": leads}


@register_node("kommo.create_lead")
async def kommo_create_lead(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new lead in Kommo CRM.

    config/input_data:
      access_token — OAuth access token (required)
      subdomain    — account subdomain (required)
      name         — lead name (required)
      status_id    — pipeline status ID (optional)
    """
    merged = {**config, **input_data}
    token = merged.get("access_token") or merged.get("api_key") or ""
    subdomain = merged.get("subdomain") or ""
    name = merged.get("name") or ""
    status_id = merged.get("status_id")

    if not subdomain:
        raise ValueError("subdomain is required for kommo.create_lead")
    if not name:
        raise ValueError("name is required for kommo.create_lead")

    headers = {"Authorization": f"Bearer {token}"}
    url = f"{_kommo_base(subdomain)}/leads"
    lead_obj: dict = {"name": name}
    if status_id is not None:
        lead_obj["status_id"] = status_id
    payload = [lead_obj]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    leads = data.get("_embedded", {}).get("leads", data)
    created = leads[0] if isinstance(leads, list) and leads else leads
    log.info("kommo.create_lead", name=name, id=created.get("id") if isinstance(created, dict) else None)
    return {"lead": created}


@register_node("kommo.list_contacts")
async def kommo_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts from Kommo CRM.

    config/input_data:
      access_token — OAuth access token (required)
      subdomain    — account subdomain (required)
      limit        — number of contacts to return (default 50)
    """
    merged = {**config, **input_data}
    token = merged.get("access_token") or merged.get("api_key") or ""
    subdomain = merged.get("subdomain") or ""
    limit = int(merged.get("limit", 50))

    if not subdomain:
        raise ValueError("subdomain is required for kommo.list_contacts")

    headers = {"Authorization": f"Bearer {token}"}
    url = f"{_kommo_base(subdomain)}/contacts"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params={"limit": limit})
        r.raise_for_status()
        data = r.json()

    contacts = data.get("_embedded", {}).get("contacts", data)
    log.info("kommo.list_contacts", subdomain=subdomain, count=len(contacts) if isinstance(contacts, list) else None)
    return {"contacts": contacts}


@register_node("kommo.create_contact")
async def kommo_create_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new contact in Kommo CRM.

    config/input_data:
      access_token         — OAuth access token (required)
      subdomain            — account subdomain (required)
      name                 — contact full name (required)
      custom_fields_values — list of custom field value objects (optional)
    """
    merged = {**config, **input_data}
    token = merged.get("access_token") or merged.get("api_key") or ""
    subdomain = merged.get("subdomain") or ""
    name = merged.get("name") or ""
    custom_fields = merged.get("custom_fields_values") or []

    if not subdomain:
        raise ValueError("subdomain is required for kommo.create_contact")
    if not name:
        raise ValueError("name is required for kommo.create_contact")

    headers = {"Authorization": f"Bearer {token}"}
    url = f"{_kommo_base(subdomain)}/contacts"
    payload = [{"name": name, "custom_fields_values": custom_fields}]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    contacts = data.get("_embedded", {}).get("contacts", data)
    created = contacts[0] if isinstance(contacts, list) and contacts else contacts
    log.info("kommo.create_contact", name=name, id=created.get("id") if isinstance(created, dict) else None)
    return {"contact": created}
