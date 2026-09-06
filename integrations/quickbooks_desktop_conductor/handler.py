"""QuickBooks Desktop Conductor integration — QB Desktop sync."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://conductor.is/api/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('secret_key', '')}", "Content-Type": "application/json"}


@register_node("quickbooks_desktop_conductor.create_customer")
async def qbd_create_customer(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    end_user_id = merged.get("end_user_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/quickbooks-desktop/customers", headers={**_headers(merged), "Conductor-End-User-Id": end_user_id}, json={
            "name": merged.get("name", ""),
            "email": merged.get("email", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("quickbooks_desktop_conductor.create_invoice")
async def qbd_create_invoice(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    end_user_id = merged.get("end_user_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/quickbooks-desktop/invoices", headers={**_headers(merged), "Conductor-End-User-Id": end_user_id}, json={
            "customer_id": merged.get("customer_id", ""),
            "line_items": merged.get("line_items", []),
        })
        r.raise_for_status()
    return r.json()
