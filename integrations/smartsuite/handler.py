"""SmartSuite integration — work management platform."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://app.smartsuite.com/api/v1"


def _headers(config: dict) -> dict:
    return {
        "Authorization": f"Token {config.get('api_key', '')}",
        "ACCOUNT-ID": config.get("account_id", ""),
        "Content-Type": "application/json",
    }


@register_node("smartsuite.create_record")
async def smartsuite_create_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    solution_id = merged.get("solution_id", "")
    app_id = merged.get("app_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/applications/{app_id}/records/", json=merged.get("fields", {}))
        r.raise_for_status()
    return r.json()


@register_node("smartsuite.get_records")
async def smartsuite_get_records(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    app_id = merged.get("app_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/applications/{app_id}/records/list/", json={"sort": []})
        r.raise_for_status()
    return {"records": r.json().get("items", [])}


@register_node("smartsuite.update_record")
async def smartsuite_update_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    app_id = merged.get("app_id", "")
    record_id = merged.get("record_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.patch(f"{BASE}/applications/{app_id}/records/{record_id}/", json=merged.get("fields", {}))
        r.raise_for_status()
    return r.json()
