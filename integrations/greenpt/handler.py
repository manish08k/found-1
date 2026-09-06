"""GreenPT integration — green energy and sustainability API."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.greenpt.io/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("greenpt.get_carbon_footprint")
async def greenpt_get_carbon_footprint(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/carbon/calculate", json={
            "activity": merged.get("activity", ""),
            "amount": merged.get("amount", 0),
            "unit": merged.get("unit", "kwh"),
        })
        r.raise_for_status()
    return r.json()


@register_node("greenpt.get_energy_data")
async def greenpt_get_energy_data(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/energy", params={"location": merged.get("location", "")})
        r.raise_for_status()
    return r.json()
