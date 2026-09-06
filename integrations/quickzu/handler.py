"""Quickzu integration — quick delivery and logistics."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.quickzu.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("quickzu.create_delivery")
async def quickzu_create_delivery(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/deliveries", json={
            "pickup": merged.get("pickup", {}),
            "dropoff": merged.get("dropoff", {}),
            "items": merged.get("items", []),
        })
        r.raise_for_status()
    return r.json()


@register_node("quickzu.track_delivery")
async def quickzu_track_delivery(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    delivery_id = merged.get("delivery_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/deliveries/{delivery_id}")
        r.raise_for_status()
    return r.json()
