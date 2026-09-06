"""Fathom integration — meeting recording and AI notes."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://fathom.video/api/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("fathom.get_calls")
async def fathom_get_calls(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/calls", params={"limit": merged.get("limit", 10)})
        r.raise_for_status()
    return {"calls": r.json()}


@register_node("fathom.get_call_transcript")
async def fathom_get_call_transcript(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    call_id = merged.get("call_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/calls/{call_id}/transcript")
        r.raise_for_status()
    return r.json()


@register_node("fathom.get_call_summary")
async def fathom_get_call_summary(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    call_id = merged.get("call_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/calls/{call_id}/summary")
        r.raise_for_status()
    return r.json()
