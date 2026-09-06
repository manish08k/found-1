"""Smoove integration — marketing automation platform."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://rest.smoove.io/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("smoove.create_contact")
async def smoove_create_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/Contacts", json={
            "Email": merged.get("email", ""),
            "FirstName": merged.get("first_name", ""),
            "LastName": merged.get("last_name", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("smoove.send_campaign")
async def smoove_send_campaign(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    campaign_id = merged.get("campaign_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/Campaigns/{campaign_id}/Send")
        r.raise_for_status()
    return r.json()
