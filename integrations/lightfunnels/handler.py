"""LightFunnels integration — sales funnel builder."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://app.lightfunnels.com/api/2021-07"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("lightfunnels.get_orders")
async def lightfunnels_get_orders(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/orders.json", params={"limit": merged.get("limit", 20)})
        r.raise_for_status()
    return {"orders": r.json().get("orders", [])}


@register_node("lightfunnels.create_order")
async def lightfunnels_create_order(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/orders.json", json={"order": merged.get("order", {})})
        r.raise_for_status()
    return r.json()
