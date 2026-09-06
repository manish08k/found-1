"""Instasent integration — SMS marketing platform."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.instasent.com/sms"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_token', '')}", "Content-Type": "application/json"}


@register_node("instasent.send_sms")
async def instasent_send_sms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(BASE, json={
            "to": merged.get("to", ""),
            "message": merged.get("message", ""),
            "from": merged.get("from_name", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("instasent.send_bulk_sms")
async def instasent_send_bulk_sms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/bulk", json={
            "recipients": merged.get("recipients", []),
            "message": merged.get("message", ""),
            "from": merged.get("from_name", ""),
        })
        r.raise_for_status()
    return r.json()
