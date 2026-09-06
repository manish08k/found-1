"""Hastewire integration — fast messaging and notifications."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.hastewire.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("hastewire.send_message")
async def hastewire_send_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/messages", json={
            "to": merged.get("to", ""),
            "message": merged.get("message", ""),
        })
        r.raise_for_status()
    return r.json()
