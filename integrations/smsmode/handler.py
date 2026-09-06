"""SMSMode integration — SMS messaging platform."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://rest.smsmode.com/sms/v1"


def _headers(config: dict) -> dict:
    return {"X-Api-Key": config.get("api_key", ""), "Content-Type": "application/json"}


@register_node("smsmode.send_sms")
async def smsmode_send_sms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/send", json={
            "recipient": merged.get("to", ""),
            "message": merged.get("message", ""),
            "sender": merged.get("from", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("smsmode.get_sms_status")
async def smsmode_get_sms_status(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    sms_id = merged.get("sms_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/{sms_id}")
        r.raise_for_status()
    return r.json()
