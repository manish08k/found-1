"""Retune integration — AI chatbot builder and deployment."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://retune.so/api/public/v1"


def _headers(config: dict) -> dict:
    return {"x-api-key": config.get("api_key", ""), "Content-Type": "application/json"}


@register_node("retune.chat")
async def retune_chat(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/chat/{merged.get('chatbot_id', '')}/response", json={
            "input": merged.get("message", ""),
            "threadId": merged.get("thread_id"),
        })
        r.raise_for_status()
    return r.json()


@register_node("retune.get_chatbots")
async def retune_get_chatbots(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/chatbots")
        r.raise_for_status()
    return {"chatbots": r.json()}
