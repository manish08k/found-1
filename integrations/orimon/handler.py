"""Orimon integration — AI chatbot and sales automation."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://app.orimon.ai/api/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("orimon.get_conversations")
async def orimon_get_conversations(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/conversations", params={"limit": merged.get("limit", 10)})
        r.raise_for_status()
    return {"conversations": r.json()}


@register_node("orimon.send_message")
async def orimon_send_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/messages", json={
            "conversation_id": merged.get("conversation_id", ""),
            "message": merged.get("message", ""),
        })
        r.raise_for_status()
    return r.json()
