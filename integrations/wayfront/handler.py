"""Wayfront business operations platform — handler for wayfront integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.wayfront.com/v1"


@register_node("wayfront.list_contacts")
async def wayfront_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/contacts", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("wayfront.list_contacts")
    return {"data": data}

@register_node("wayfront.create_contact")
async def wayfront_create_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a contact.

    config/input_data:
      api_key — API key or token (required)
      name — (required)
      email — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    name = merged.get("name") or ""
    email = merged.get("email") or ""
    if not name or not email:
        raise ValueError("name, email required for wayfront.create_contact")
    payload = {"name": name, "email": email}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/contacts", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("wayfront.create_contact")
    return {"data": data}

@register_node("wayfront.list_tasks")
async def wayfront_list_tasks(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List tasks.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/tasks", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("wayfront.list_tasks")
    return {"data": data}
