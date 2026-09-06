"""Qawafel integration — Arabic e-commerce and logistics platform."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.qawafel.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("qawafel.create_shipment")
async def qawafel_create_shipment(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/shipments", json={
            "recipient": merged.get("recipient", {}),
            "packages": merged.get("packages", []),
        })
        r.raise_for_status()
    return r.json()


@register_node("qawafel.track_shipment")
async def qawafel_track_shipment(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    tracking_id = merged.get("tracking_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/shipments/{tracking_id}/track")
        r.raise_for_status()
    return r.json()
