"""Tenzo integration — restaurant analytics and labor management."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.tenzo.io/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("tenzo.get_sales")
async def tenzo_get_sales(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/sales", params={
            "from": merged.get("from_date", ""),
            "to": merged.get("to_date", ""),
            "location_id": merged.get("location_id", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("tenzo.get_labor")
async def tenzo_get_labor(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/labor", params={"from": merged.get("from_date", ""), "to": merged.get("to_date", "")})
        r.raise_for_status()
    return r.json()
