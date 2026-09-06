"""Teable integration — modern database and spreadsheet."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://app.teable.io/api"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("teable.get_records")
async def teable_get_records(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    table_id = merged.get("table_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/table/{table_id}/record", params={"take": merged.get("limit", 20)})
        r.raise_for_status()
    return {"records": r.json().get("records", [])}


@register_node("teable.create_record")
async def teable_create_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    table_id = merged.get("table_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/table/{table_id}/record", json={"records": [{"fields": merged.get("fields", {})}]})
        r.raise_for_status()
    return r.json()


@register_node("teable.update_record")
async def teable_update_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    table_id = merged.get("table_id", "")
    record_id = merged.get("record_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.patch(f"{BASE}/table/{table_id}/record/{record_id}", json={"fields": merged.get("fields", {})})
        r.raise_for_status()
    return r.json()
