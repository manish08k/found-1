"""Retell AI integration — AI voice calling platform."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.retellai.com"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("retell_ai.create_phone_call")
async def retell_ai_create_phone_call(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/v2/create-phone-call", json={
            "from_number": merged.get("from_number", ""),
            "to_number": merged.get("to_number", ""),
            "agent_id": merged.get("agent_id", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("retell_ai.get_call")
async def retell_ai_get_call(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    call_id = merged.get("call_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/v2/get-call/{call_id}")
        r.raise_for_status()
    return r.json()


@register_node("retell_ai.list_calls")
async def retell_ai_list_calls(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/v2/list-calls", params={"limit": merged.get("limit", 20)})
        r.raise_for_status()
    return {"calls": r.json()}
