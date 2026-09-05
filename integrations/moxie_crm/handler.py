"""Moxie freelancer CRM integration — contacts and projects."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

MOXIE_BASE = "https://api.moxie.us/v1"


@register_node("moxie_crm.list_contacts")
async def moxie_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts from Moxie CRM.

    config/input_data:
      api_key — Moxie API key (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{MOXIE_BASE}/contacts"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()

    contacts = data.get("data", data) if isinstance(data, dict) else data
    log.info("moxie_crm.list_contacts", count=len(contacts) if isinstance(contacts, list) else None)
    return {"contacts": contacts}


@register_node("moxie_crm.create_contact")
async def moxie_create_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a contact in Moxie CRM.

    config/input_data:
      api_key    — Moxie API key (required)
      first_name — first name (required)
      last_name  — last name
      email      — email address
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    fn = merged.get("first_name") or ""
    ln = merged.get("last_name") or ""
    email = merged.get("email") or ""

    if not fn:
        raise ValueError("first_name is required for moxie_crm.create_contact")

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{MOXIE_BASE}/contacts"
    payload: dict = {"firstName": fn, "lastName": ln}
    if email:
        payload["email"] = email

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    contact = data.get("data", data) if isinstance(data, dict) else data
    log.info("moxie_crm.create_contact", first_name=fn, last_name=ln)
    return {"contact": contact}


@register_node("moxie_crm.list_projects")
async def moxie_list_projects(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List projects from Moxie CRM.

    config/input_data:
      api_key — Moxie API key (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{MOXIE_BASE}/projects"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()

    projects = data.get("data", data) if isinstance(data, dict) else data
    log.info("moxie_crm.list_projects", count=len(projects) if isinstance(projects, list) else None)
    return {"projects": projects}
