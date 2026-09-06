"""Freshsales integration — CRM and sales platform."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _base(config: dict) -> str:
    return f"https://{config.get('domain', '')}.myfreshworks.com/crm/sales/api"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Token token={config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("freshsales.create_contact")
async def freshsales_create_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{_base(merged)}/contacts", json={"contact": {
            "first_name": merged.get("first_name", ""),
            "last_name": merged.get("last_name", ""),
            "email": merged.get("email", ""),
            "mobile_number": merged.get("phone", ""),
        }})
        r.raise_for_status()
    return r.json()


@register_node("freshsales.create_deal")
async def freshsales_create_deal(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{_base(merged)}/deals", json={"deal": {
            "name": merged.get("name", ""),
            "amount": merged.get("amount", 0),
            "sales_account_id": merged.get("account_id"),
        }})
        r.raise_for_status()
    return r.json()


@register_node("freshsales.get_contacts")
async def freshsales_get_contacts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{_base(merged)}/contacts", params={"per_page": merged.get("limit", 20)})
        r.raise_for_status()
    return {"contacts": r.json().get("contacts", [])}
