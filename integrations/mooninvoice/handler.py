"""MoonInvoice integration — invoice creation and billing."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.mooninvoice.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("mooninvoice.create_invoice")
async def mooninvoice_create_invoice(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/invoices", json={
            "client_id": merged.get("client_id", ""),
            "items": merged.get("items", []),
            "due_date": merged.get("due_date", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("mooninvoice.get_invoices")
async def mooninvoice_get_invoices(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/invoices")
        r.raise_for_status()
    return {"invoices": r.json()}
