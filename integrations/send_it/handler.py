"""Send It integration — parcel and delivery services."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.sendit.co.za/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("send_it.create_waybill")
async def send_it_create_waybill(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/waybills", json={
            "sender": merged.get("sender", {}),
            "receiver": merged.get("receiver", {}),
            "parcels": merged.get("parcels", []),
        })
        r.raise_for_status()
    return r.json()


@register_node("send_it.track_shipment")
async def send_it_track_shipment(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    waybill_id = merged.get("waybill_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/tracking/{waybill_id}")
        r.raise_for_status()
    return r.json()
