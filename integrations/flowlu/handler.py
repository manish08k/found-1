"""Flowlu integration — CRM and project management."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _base(config: dict) -> str:
    return f"https://{config.get('workspace', '')}.flowlu.com/api/v1"


def _headers(config: dict) -> dict:
    return {"Content-Type": "application/json"}


def _params(config: dict) -> dict:
    return {"api_key": config.get("api_key", "")}


@register_node("flowlu.create_contact")
async def flowlu_create_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{_base(merged)}/crm/customer/create", params=_params(merged), json={
            "name": merged.get("name", ""),
            "email": merged.get("email", ""),
            "phone": merged.get("phone", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("flowlu.create_opportunity")
async def flowlu_create_opportunity(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{_base(merged)}/crm/opportunity/create", params=_params(merged), json={
            "name": merged.get("name", ""),
            "customer_id": merged.get("customer_id", ""),
            "amount": merged.get("amount", 0),
        })
        r.raise_for_status()
    return r.json()
