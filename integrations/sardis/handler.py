"""Sardis integration — real estate data and analytics."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.sardis.io/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("sardis.search_properties")
async def sardis_search_properties(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/properties/search", json={
            "location": merged.get("location", ""),
            "min_price": merged.get("min_price"),
            "max_price": merged.get("max_price"),
        })
        r.raise_for_status()
    return {"properties": r.json()}


@register_node("sardis.get_property")
async def sardis_get_property(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    property_id = merged.get("property_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/properties/{property_id}")
        r.raise_for_status()
    return r.json()
