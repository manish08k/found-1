"""Saastic integration — SaaS metrics and analytics."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.saastic.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("saastic.get_metrics")
async def saastic_get_metrics(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/metrics", params={"period": merged.get("period", "month")})
        r.raise_for_status()
    return r.json()


@register_node("saastic.get_customers")
async def saastic_get_customers(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/customers")
        r.raise_for_status()
    return {"customers": r.json()}
