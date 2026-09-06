"""Thankster integration — personalized thank you card automation."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://www.thankster.com/api/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Token {config.get('api_token', '')}", "Content-Type": "application/json"}


@register_node("thankster.send_card")
async def thankster_send_card(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/cards", json={
            "recipient_name": merged.get("recipient_name", ""),
            "recipient_address": merged.get("recipient_address", {}),
            "message": merged.get("message", ""),
            "template_id": merged.get("template_id", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("thankster.get_card_status")
async def thankster_get_card_status(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    card_id = merged.get("card_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/cards/{card_id}")
        r.raise_for_status()
    return r.json()
