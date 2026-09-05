"""Wealthbox financial CRM integration — contacts and tasks."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

WEALTHBOX_BASE = "https://api.crmworkspace.com/v1"


@register_node("wealthbox.list_contacts")
async def wealthbox_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts from Wealthbox CRM.

    config/input_data:
      api_key  — Wealthbox access token (required)
      page     — page number (default 1)
      per_page — results per page (default 25)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    page = int(merged.get("page", 1))
    per_page = int(merged.get("per_page", 25))

    headers = {"ACCESS_TOKEN": api_key}
    url = f"{WEALTHBOX_BASE}/contacts"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params={"page": page, "per_page": per_page})
        r.raise_for_status()
        data = r.json()

    contacts = data.get("contacts", data)
    log.info("wealthbox.list_contacts", page=page, count=len(contacts) if isinstance(contacts, list) else None)
    return {"contacts": contacts, "page": page}


@register_node("wealthbox.create_contact")
async def wealthbox_create_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new person contact in Wealthbox CRM.

    config/input_data:
      api_key    — Wealthbox access token (required)
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
        raise ValueError("first_name is required for wealthbox.create_contact")

    headers = {"ACCESS_TOKEN": api_key}
    url = f"{WEALTHBOX_BASE}/contacts"
    payload: dict = {
        "contact": {
            "type": "Person",
            "first_name": fn,
            "last_name": ln,
        }
    }
    if email:
        payload["contact"]["email_addresses"] = [{"address": email}]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    contact = data.get("contact", data)
    log.info("wealthbox.create_contact", first_name=fn, last_name=ln, id=contact.get("id") if isinstance(contact, dict) else None)
    return {"contact": contact}


@register_node("wealthbox.list_tasks")
async def wealthbox_list_tasks(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List tasks from Wealthbox CRM.

    config/input_data:
      api_key  — Wealthbox access token (required)
      page     — page number (default 1)
      per_page — results per page (default 25)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    page = int(merged.get("page", 1))
    per_page = int(merged.get("per_page", 25))

    headers = {"ACCESS_TOKEN": api_key}
    url = f"{WEALTHBOX_BASE}/tasks"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params={"page": page, "per_page": per_page})
        r.raise_for_status()
        data = r.json()

    tasks = data.get("tasks", data)
    log.info("wealthbox.list_tasks", page=page, count=len(tasks) if isinstance(tasks, list) else None)
    return {"tasks": tasks, "page": page}
