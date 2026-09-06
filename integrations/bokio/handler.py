"""Bokio accounting and invoicing — handler for bokio integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.bokio.se/v1"


@register_node("bokio.list_invoices")
async def bokio_list_invoices(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
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
    log.info("bokio.list_invoices")
    return {"data": data}

@register_node("bokio.create_invoice")
async def bokio_create_invoice(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create an invoice.

    config/input_data:
      api_key — API key or token (required)
      customer_id — (required)
      items — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    customer_id = merged.get("customer_id") or ""
    items = merged.get("items") or ""
    if not customer_id or not items:
        raise ValueError("customer_id, items required for bokio.create_invoice")
    payload = {"customer_id": customer_id, "items": items}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/invoices", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("bokio.create_invoice")
    return {"data": data}

@register_node("bokio.get_invoice")
async def bokio_get_invoice(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get invoice details.

    config/input_data:
      api_key — API key or token (required)
      invoice_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    invoice_id = merged.get("invoice_id") or ""
    if not invoice_id:
        raise ValueError("invoice_id required for bokio.get_invoice")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/invoices/{invoice_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("bokio.get_invoice")
    return {"data": data}
