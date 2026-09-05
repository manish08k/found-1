"""NinjaPipe CRM integration — pipelines and contacts."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

NINJAPIPE_BASE = "https://api.ninjapipe.com/v1"


@register_node("ninjapipe.list_pipelines")
async def ninjapipe_list_pipelines(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all pipelines from NinjaPipe.

    config/input_data:
      api_key — NinjaPipe API key (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{NINJAPIPE_BASE}/pipelines"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()

    pipelines = data.get("data", data) if isinstance(data, dict) else data
    log.info("ninjapipe.list_pipelines", count=len(pipelines) if isinstance(pipelines, list) else None)
    return {"pipelines": pipelines}


@register_node("ninjapipe.list_contacts")
async def ninjapipe_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts from NinjaPipe.

    config/input_data:
      api_key — NinjaPipe API key (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{NINJAPIPE_BASE}/contacts"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()

    contacts = data.get("data", data) if isinstance(data, dict) else data
    log.info("ninjapipe.list_contacts", count=len(contacts) if isinstance(contacts, list) else None)
    return {"contacts": contacts}


@register_node("ninjapipe.create_contact")
async def ninjapipe_create_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a contact in NinjaPipe.

    config/input_data:
      api_key — NinjaPipe API key (required)
      name    — contact full name (required)
      email   — contact email (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    name = merged.get("name") or ""
    email = merged.get("email") or ""

    if not name:
        raise ValueError("name is required for ninjapipe.create_contact")
    if not email:
        raise ValueError("email is required for ninjapipe.create_contact")

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{NINJAPIPE_BASE}/contacts"
    payload = {"name": name, "email": email}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    contact = data.get("data", data) if isinstance(data, dict) else data
    log.info("ninjapipe.create_contact", name=name, email=email)
    return {"contact": contact}
