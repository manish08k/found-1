"""DIMO integration — connected vehicle data platform."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.dimo.zone/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('access_token', '')}", "Content-Type": "application/json"}


@register_node("dimo.get_vehicles")
async def dimo_get_vehicles(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/vehicles")
        r.raise_for_status()
    return {"vehicles": r.json()}


@register_node("dimo.get_vehicle_signals")
async def dimo_get_vehicle_signals(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    vehicle_id = merged.get("vehicle_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/vehicles/{vehicle_id}/signals")
        r.raise_for_status()
    return r.json()
