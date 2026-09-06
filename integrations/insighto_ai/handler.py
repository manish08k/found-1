"""Insighto AI integration — AI-powered chat and voice agents."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://app.insighto.ai/api/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("insighto_ai.create_conversation")
async def insighto_ai_create_conversation(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/conversations", json={
            "agent_id": merged.get("agent_id", ""),
            "user_id": merged.get("user_id", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("insighto_ai.send_message")
async def insighto_ai_send_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    conv_id = merged.get("conversation_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/conversations/{conv_id}/messages", json={
            "content": merged.get("message", ""),
        })
        r.raise_for_status()
    return r.json()
