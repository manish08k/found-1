"""Kissflow integration — work management and process automation."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.kissflow.com/workflow/2"


def _headers(config: dict) -> dict:
    return {"X-Api-Key": config.get("api_key", ""), "Content-Type": "application/json"}


@register_node("kissflow.create_item")
async def kissflow_create_item(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    account_id = merged.get("account_id", "")
    process_id = merged.get("process_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/{account_id}/process/{process_id}/item", json=merged.get("fields", {}))
        r.raise_for_status()
    return r.json()


@register_node("kissflow.get_items")
async def kissflow_get_items(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    account_id = merged.get("account_id", "")
    process_id = merged.get("process_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/{account_id}/process/{process_id}/item")
        r.raise_for_status()
    return {"items": r.json()}
