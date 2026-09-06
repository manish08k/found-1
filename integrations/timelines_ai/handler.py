"""TimelinesAI integration — WhatsApp CRM and messaging automation."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://app.timelines.ai/api"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("timelines_ai.send_message")
async def timelines_ai_send_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/messages", json={
            "phone": merged.get("phone", ""),
            "message": merged.get("message", ""),
            "account_id": merged.get("account_id", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("timelines_ai.get_conversations")
async def timelines_ai_get_conversations(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/conversations", params={
            "account_id": merged.get("account_id", ""),
            "limit": merged.get("limit", 50),
        })
        r.raise_for_status()
    return {"conversations": r.json()}


@register_node("timelines_ai.add_contact")
async def timelines_ai_add_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/contacts", json={
            "phone": merged.get("phone", ""),
            "name": merged.get("name", ""),
            "email": merged.get("email", ""),
        })
        r.raise_for_status()
    return r.json()
