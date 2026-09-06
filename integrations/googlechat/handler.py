"""Google Chat integration — messaging and rooms."""
import httpx
import structlog
from core.execution_engine import register_node
from oauth.flow import get_access_token

log = structlog.get_logger(__name__)
BASE = "https://chat.googleapis.com/v1"


async def _headers(credential_id: str, db) -> dict:
    token = await get_access_token(credential_id, db)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@register_node("googlechat.send_message")
async def googlechat_send_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    space_name = merged.get("space_name", "")
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.post(f"{BASE}/{space_name}/messages", json={"text": merged.get("text", "")})
        r.raise_for_status()
    return r.json()


@register_node("googlechat.list_spaces")
async def googlechat_list_spaces(config: dict, input_data: dict, credential_id: str, db) -> dict:
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.get(f"{BASE}/spaces")
        r.raise_for_status()
    return {"spaces": r.json().get("spaces", [])}


@register_node("googlechat.send_webhook_message")
async def googlechat_send_webhook_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    webhook_url = merged.get("webhook_url", "")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(webhook_url, json={"text": merged.get("text", "")})
        r.raise_for_status()
    return {"ok": True}
