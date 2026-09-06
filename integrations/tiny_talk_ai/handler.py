"""TinyTalk AI integration — AI chatbot builder and deployment."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.tinytalk.ai/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("tiny_talk_ai.send_message")
async def tiny_talk_ai_send_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/chat", json={
            "bot_id": merged.get("bot_id", ""),
            "message": merged.get("message", ""),
            "session_id": merged.get("session_id", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("tiny_talk_ai.create_bot")
async def tiny_talk_ai_create_bot(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/bots", json={
            "name": merged.get("name", ""),
            "description": merged.get("description", ""),
            "model": merged.get("model", "gpt-4"),
        })
        r.raise_for_status()
    return r.json()


@register_node("tiny_talk_ai.list_bots")
async def tiny_talk_ai_list_bots(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/bots")
        r.raise_for_status()
    return {"bots": r.json()}
