"""ConnectUC integration — unified communications platform."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.connectuc.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("connectuc.send_sms")
async def connectuc_send_sms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/sms", json={
            "to": merged.get("to", ""),
            "message": merged.get("message", ""),
            "from": merged.get("from_number", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("connectuc.make_call")
async def connectuc_make_call(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/calls", json={
            "to": merged.get("to", ""),
            "from": merged.get("from_number", ""),
        })
        r.raise_for_status()
    return r.json()
