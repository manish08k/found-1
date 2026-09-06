"""Wafeq accounting software for MENA — handler for wafeq integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.wafeq.com/v1"


@register_node("wafeq.list_invoices")
async def wafeq_list_invoices(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
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
    log.info("wafeq.list_invoices")
    return {"data": data}

@register_node("wafeq.create_invoice")
async def wafeq_create_invoice(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create an invoice.

    config/input_data:
      api_key — API key or token (required)
      contact_id — (required)
      line_items — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    contact_id = merged.get("contact_id") or ""
    line_items = merged.get("line_items") or ""
    if not contact_id or not line_items:
        raise ValueError("contact_id, line_items required for wafeq.create_invoice")
    payload = {"contact_id": contact_id, "line_items": line_items}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/invoices", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("wafeq.create_invoice")
    return {"data": data}

@register_node("wafeq.list_contacts")
async def wafeq_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
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
    log.info("wafeq.list_contacts")
    return {"data": data}

@register_node("wafeq.create_contact")
async def wafeq_create_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a contact.

    config/input_data:
      api_key — API key or token (required)
      name — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    name = merged.get("name") or ""
    if not name:
        raise ValueError("name required for wafeq.create_contact")
    payload = {"name": name}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/contacts", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("wafeq.create_contact")
    return {"data": data}
