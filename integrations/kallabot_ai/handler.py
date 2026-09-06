"""Kallabot AI integration — AI voice calling agent."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.kallabot.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("kallabot_ai.make_call")
async def kallabot_ai_make_call(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/calls", json={
            "to_phone_number": merged.get("phone", ""),
            "from_phone_number": merged.get("from_phone", ""),
            "task": merged.get("task", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("kallabot_ai.get_call")
async def kallabot_ai_get_call(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    call_id = merged.get("call_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/calls/{call_id}")
        r.raise_for_status()
    return r.json()
