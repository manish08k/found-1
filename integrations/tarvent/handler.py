"""Tarvent integration — email marketing and automation."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.tarvent.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("tarvent.create_contact")
async def tarvent_create_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/contacts", json={
            "emailAddress": merged.get("email", ""),
            "firstName": merged.get("first_name", ""),
            "lastName": merged.get("last_name", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("tarvent.send_campaign")
async def tarvent_send_campaign(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    campaign_id = merged.get("campaign_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/campaigns/{campaign_id}/send")
        r.raise_for_status()
    return r.json()
