"""Pollybot AI integration — AI customer engagement chatbot."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.pollybot.ai/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("pollybot_ai.send_message")
async def pollybot_ai_send_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/chat", json={
            "bot_id": merged.get("bot_id", ""),
            "session_id": merged.get("session_id", ""),
            "message": merged.get("message", ""),
        })
        r.raise_for_status()
    return r.json()
