"""RapidText AI integration — AI SMS and messaging automation."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.rapidtext.ai/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("rapidtext_ai.send_sms")
async def rapidtext_ai_send_sms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/messages", json={
            "to": merged.get("to", ""),
            "message": merged.get("message", ""),
            "from": merged.get("from_number", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("rapidtext_ai.get_conversations")
async def rapidtext_ai_get_conversations(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/conversations")
        r.raise_for_status()
    return {"conversations": r.json()}
