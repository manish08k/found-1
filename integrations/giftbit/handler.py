"""Giftbit integration — digital gift card distribution."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.giftbit.com/papi/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_token', '')}", "Content-Type": "application/json"}


@register_node("giftbit.create_campaign")
async def giftbit_create_campaign(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/campaign", json={
            "delivery": {"delivery_type": "EMAIL"},
            "contacts": merged.get("contacts", []),
            "choices": merged.get("choices", []),
            "message_subject": merged.get("subject", "Your gift"),
        })
        r.raise_for_status()
    return r.json()


@register_node("giftbit.get_gift")
async def giftbit_get_gift(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    gift_id = merged.get("gift_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/gift/{gift_id}")
        r.raise_for_status()
    return r.json()
