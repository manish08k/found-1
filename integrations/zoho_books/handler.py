"""Zoho Books accounting software — handler for zoho_books integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://www.zohoapis.com/books/v3"


@register_node("zoho_books.list_invoices")
async def zoho_books_list_invoices(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List invoices.

    config/input_data:
      api_key — API key or token (required)
      organization_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    organization_id = merged.get("organization_id") or ""
    if not organization_id:
        raise ValueError("organization_id required for zoho_books.list_invoices")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/invoices", headers=headers, params={"organization_id": organization_id})
        r.raise_for_status()
        data = r.json()
    log.info("zoho_books.list_invoices")
    return {"data": data}

@register_node("zoho_books.create_invoice")
async def zoho_books_create_invoice(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create an invoice.

    config/input_data:
      api_key — API key or token (required)
      organization_id — (required)
      customer_id — (required)
      line_items — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    organization_id = merged.get("organization_id") or ""
    customer_id = merged.get("customer_id") or ""
    line_items = merged.get("line_items") or ""
    if not organization_id or not customer_id or not line_items:
        raise ValueError("organization_id, customer_id, line_items required for zoho_books.create_invoice")
    payload = {"organization_id": organization_id, "customer_id": customer_id, "line_items": line_items}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/invoices", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("zoho_books.create_invoice")
    return {"data": data}

@register_node("zoho_books.list_contacts")
async def zoho_books_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts.

    config/input_data:
      api_key — API key or token (required)
      organization_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    organization_id = merged.get("organization_id") or ""
    if not organization_id:
        raise ValueError("organization_id required for zoho_books.list_contacts")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/contacts", headers=headers, params={"organization_id": organization_id})
        r.raise_for_status()
        data = r.json()
    log.info("zoho_books.list_contacts")
    return {"data": data}

@register_node("zoho_books.create_contact")
async def zoho_books_create_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a contact.

    config/input_data:
      api_key — API key or token (required)
      organization_id — (required)
      contact_name — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    organization_id = merged.get("organization_id") or ""
    contact_name = merged.get("contact_name") or ""
    if not organization_id or not contact_name:
        raise ValueError("organization_id, contact_name required for zoho_books.create_contact")
    payload = {"organization_id": organization_id, "contact_name": contact_name}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/contacts", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("zoho_books.create_contact")
    return {"data": data}
