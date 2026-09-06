"""Microsoft Teams Bot integration — bot messaging and activities."""
import httpx
import structlog
from core.execution_engine import register_node
from oauth.flow import get_access_token

log = structlog.get_logger(__name__)
BASE = "https://graph.microsoft.com/v1.0"


async def _headers(credential_id: str, db) -> dict:
    token = await get_access_token(credential_id, db)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@register_node("microsoft_teams_bot.send_message")
async def teams_bot_send_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    headers = await _headers(credential_id, db)
    chat_id = merged.get("chat_id", "")
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.post(f"{BASE}/chats/{chat_id}/messages", json={
            "body": {"content": merged.get("message", ""), "contentType": "text"}
        })
        r.raise_for_status()
    return r.json()


@register_node("microsoft_teams_bot.get_chats")
async def teams_bot_get_chats(config: dict, input_data: dict, credential_id: str, db) -> dict:
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.get(f"{BASE}/me/chats")
        r.raise_for_status()
    return {"chats": r.json().get("value", [])}
