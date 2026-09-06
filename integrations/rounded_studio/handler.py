"""Rounded Studio integration — financial management for freelancers."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.rounded.com.au/api/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("rounded_studio.create_invoice")
async def rounded_studio_create_invoice(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/invoices", json={
            "client_id": merged.get("client_id", ""),
            "line_items": merged.get("line_items", []),
            "due_date": merged.get("due_date", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("rounded_studio.get_clients")
async def rounded_studio_get_clients(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/clients")
        r.raise_for_status()
    return {"clients": r.json()}
