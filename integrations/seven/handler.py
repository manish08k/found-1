"""Seven (SMS77) integration — SMS and voice messaging."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://gateway.seven.io/api"


def _headers(config: dict) -> dict:
    return {"X-Api-Key": config.get("api_key", ""), "Content-Type": "application/json"}


@register_node("seven.send_sms")
async def seven_send_sms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/sms", json={
            "to": merged.get("to", ""),
            "text": merged.get("text", ""),
            "from": merged.get("from", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("seven.lookup_number")
async def seven_lookup_number(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/lookup", json={
            "number": merged.get("number", ""),
            "type": merged.get("lookup_type", "format"),
        })
        r.raise_for_status()
    return r.json()
