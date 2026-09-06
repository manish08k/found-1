"""Octopush SMS integration — SMS marketing and notifications."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.octopush.com/v1/public"


def _headers(config: dict) -> dict:
    return {
        "api-login": config.get("api_login", ""),
        "api-key": config.get("api_key", ""),
        "Content-Type": "application/json",
    }


@register_node("octopush_sms.send_sms")
async def octopush_sms_send_sms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/sms-campaign/send", json={
            "recipients": [{"phone_number": merged.get("phone", "")}],
            "text": merged.get("message", ""),
            "sender": merged.get("sender", ""),
        })
        r.raise_for_status()
    return r.json()
