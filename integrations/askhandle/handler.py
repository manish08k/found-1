"""AskHandle integration — AI-powered customer support."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.askhandle.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("askhandle.create_conversation")
async def askhandle_create_conversation(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/conversations", json={
            "message": merged.get("message", ""),
            "bot_id": merged.get("bot_id", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("askhandle.send_message")
async def askhandle_send_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    conversation_id = merged.get("conversation_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/conversations/{conversation_id}/messages", json={
            "message": merged.get("message", ""),
        })
        r.raise_for_status()
    return r.json()
