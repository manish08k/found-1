"""Bexio Swiss business software — handler for bexio integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.bexio.com/2.0"


@register_node("bexio.list_contacts")
async def bexio_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/contact", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("bexio.list_contacts")
    return {"data": data}

@register_node("bexio.create_contact")
async def bexio_create_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a contact.

    config/input_data:
      api_key — API key or token (required)
      name_1 — (required)
      contact_type_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    name_1 = merged.get("name_1") or ""
    contact_type_id = merged.get("contact_type_id") or ""
    if not name_1 or not contact_type_id:
        raise ValueError("name_1, contact_type_id required for bexio.create_contact")
    payload = {"name_1": name_1, "contact_type_id": contact_type_id}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/contact", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("bexio.create_contact")
    return {"data": data}

@register_node("bexio.list_invoices")
async def bexio_list_invoices(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List invoices.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/kb_invoice", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("bexio.list_invoices")
    return {"data": data}

@register_node("bexio.create_invoice")
async def bexio_create_invoice(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create an invoice.

    config/input_data:
      api_key — API key or token (required)
      title — (required)
      contact_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    title = merged.get("title") or ""
    contact_id = merged.get("contact_id") or ""
    if not title or not contact_id:
        raise ValueError("title, contact_id required for bexio.create_invoice")
    payload = {"title": title, "contact_id": contact_id}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/kb_invoice", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("bexio.create_invoice")
    return {"data": data}
