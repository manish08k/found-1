"""HeyMarket SMS integration — business SMS messaging."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://app.heymarket.com/api/v1"


def _headers(config: dict) -> dict:
    return {"Api-Key": config.get("api_key", ""), "Content-Type": "application/json"}


@register_node("heymarket_sms.send_message")
async def heymarket_send_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/messages", json={
            "phone_number": merged.get("phone", ""),
            "message": merged.get("message", ""),
            "inbox_id": merged.get("inbox_id", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("heymarket_sms.get_conversations")
async def heymarket_get_conversations(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/conversations", params={"limit": merged.get("limit", 20)})
        r.raise_for_status()
    return {"conversations": r.json()}
