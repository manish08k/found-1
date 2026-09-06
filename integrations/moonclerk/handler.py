"""MoonClerk integration — recurring payment management."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.moonclerk.com/v1"


def _headers(config: dict) -> dict:
    return {
        "Authorization": f"Token {config.get('api_key', '')}",
        "Accept": "application/vnd.moonclerk+json;version=1",
        "Content-Type": "application/json",
    }


@register_node("moonclerk.get_payments")
async def moonclerk_get_payments(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/payments", params={"count": merged.get("limit", 20)})
        r.raise_for_status()
    return {"payments": r.json().get("payments", [])}


@register_node("moonclerk.get_customers")
async def moonclerk_get_customers(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/customers", params={"count": merged.get("limit", 20)})
        r.raise_for_status()
    return {"customers": r.json().get("customers", [])}
