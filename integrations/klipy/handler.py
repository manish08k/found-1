"""Klipy CRM and accounting automation — handler for klipy integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.klipy.com/v1"


@register_node("klipy.list_contacts")
async def klipy_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
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
    log.info("klipy.list_contacts")
    return {"data": data}

@register_node("klipy.create_contact")
async def klipy_create_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
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
        raise ValueError("name, email required for klipy.create_contact")
    payload = {"name": name, "email": email}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/contacts", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("klipy.create_contact")
    return {"data": data}

@register_node("klipy.list_invoices")
async def klipy_list_invoices(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List invoices.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/invoices", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("klipy.list_invoices")
    return {"data": data}
