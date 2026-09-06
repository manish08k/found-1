"""JustInvoice integration — invoice generation and management."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.justinvoice.net/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("just_invoice.create_invoice")
async def just_invoice_create_invoice(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/invoices", json={
            "client_name": merged.get("client_name", ""),
            "client_email": merged.get("client_email", ""),
            "items": merged.get("items", []),
            "due_date": merged.get("due_date", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("just_invoice.send_invoice")
async def just_invoice_send_invoice(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    invoice_id = merged.get("invoice_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/invoices/{invoice_id}/send", json={"email": merged.get("email", "")})
        r.raise_for_status()
    return r.json()
