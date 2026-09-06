"""Telnyx integration — cloud communications platform."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.telnyx.com/v2"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("telnyx.send_sms")
async def telnyx_send_sms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/messages", json={
            "from": merged.get("from_number", ""),
            "to": merged.get("to", ""),
            "text": merged.get("text", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("telnyx.make_call")
async def telnyx_make_call(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/calls", json={
            "connection_id": merged.get("connection_id", ""),
            "to": merged.get("to", ""),
            "from": merged.get("from_number", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("telnyx.get_messages")
async def telnyx_get_messages(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/messages", params={"page[size]": merged.get("limit", 20)})
        r.raise_for_status()
    return {"messages": r.json().get("data", [])}
