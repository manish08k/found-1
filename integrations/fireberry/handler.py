"""Fireberry integration — CRM platform."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.fireberry.com/api"


def _headers(config: dict) -> dict:
    return {"token": config.get("api_token", ""), "Content-Type": "application/json"}


@register_node("fireberry.create_record")
async def fireberry_create_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    object_type = merged.get("object_type", "contact")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/{object_type}", json=merged.get("fields", {}))
        r.raise_for_status()
    return r.json()


@register_node("fireberry.get_record")
async def fireberry_get_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    object_type = merged.get("object_type", "contact")
    record_id = merged.get("record_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/{object_type}/{record_id}")
        r.raise_for_status()
    return r.json()
