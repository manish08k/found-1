"""Returning AI integration — customer win-back automation."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.returning.ai/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("returning_ai.trigger_winback")
async def returning_ai_trigger_winback(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/winback", json={
            "customer_email": merged.get("email", ""),
            "customer_name": merged.get("name", ""),
            "last_purchase_date": merged.get("last_purchase_date", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("returning_ai.get_campaigns")
async def returning_ai_get_campaigns(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/campaigns")
        r.raise_for_status()
    return {"campaigns": r.json()}
