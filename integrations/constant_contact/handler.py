"""Constant Contact integration — email marketing."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.cc.email/v3"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('access_token', '')}", "Content-Type": "application/json"}


@register_node("constant_contact.create_contact")
async def cc_create_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/contacts", json={
            "email_address": {"address": merged.get("email", ""), "permission_to_send": "implicit"},
            "first_name": merged.get("first_name", ""),
            "last_name": merged.get("last_name", ""),
            "list_memberships": merged.get("list_ids", []),
        })
        r.raise_for_status()
    return r.json()


@register_node("constant_contact.send_email_campaign")
async def cc_send_email_campaign(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    campaign_id = merged.get("campaign_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/emails/activities/send", json={
            "campaign_id": campaign_id,
            "scheduled_date": merged.get("scheduled_date", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("constant_contact.get_contact_lists")
async def cc_get_contact_lists(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/contact_lists")
        r.raise_for_status()
    return {"lists": r.json().get("lists", [])}
