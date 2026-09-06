"""Respaid integration — accounts receivable and debt collection."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.respaid.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("respaid.create_claim")
async def respaid_create_claim(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/claims", json={
            "debtor_email": merged.get("debtor_email", ""),
            "debtor_name": merged.get("debtor_name", ""),
            "amount": merged.get("amount", 0),
            "currency": merged.get("currency", "USD"),
            "description": merged.get("description", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("respaid.get_claims")
async def respaid_get_claims(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/claims", params={"limit": merged.get("limit", 20)})
        r.raise_for_status()
    return {"claims": r.json()}
