"""Zoho Invoice online invoicing — handler for zoho_invoice integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://www.zohoapis.com/invoice/v3"


@register_node("zoho_invoice.list_invoices")
async def zoho_invoice_list_invoices(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
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
        raise ValueError("organization_id required for zoho_invoice.list_invoices")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/invoices", headers=headers, params={"organization_id": organization_id})
        r.raise_for_status()
        data = r.json()
    log.info("zoho_invoice.list_invoices")
    return {"data": data}

@register_node("zoho_invoice.create_invoice")
async def zoho_invoice_create_invoice(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create an invoice.

    config/input_data:
      api_key — API key or token (required)
      organization_id — (required)
      customer_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    organization_id = merged.get("organization_id") or ""
    customer_id = merged.get("customer_id") or ""
    if not organization_id or not customer_id:
        raise ValueError("organization_id, customer_id required for zoho_invoice.create_invoice")
    payload = {"organization_id": organization_id, "customer_id": customer_id}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/invoices", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("zoho_invoice.create_invoice")
    return {"data": data}

@register_node("zoho_invoice.get_invoice")
async def zoho_invoice_get_invoice(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get invoice details.

    config/input_data:
      api_key — API key or token (required)
      organization_id — (required)
      invoice_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    organization_id = merged.get("organization_id") or ""
    invoice_id = merged.get("invoice_id") or ""
    if not organization_id or not invoice_id:
        raise ValueError("organization_id, invoice_id required for zoho_invoice.get_invoice")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/invoices/{invoice_id}", headers=headers, params={"organization_id": organization_id})
        r.raise_for_status()
        data = r.json()
    log.info("zoho_invoice.get_invoice")
    return {"data": data}
