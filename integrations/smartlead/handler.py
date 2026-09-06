"""Smartlead integration — cold email outreach automation."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://server.smartlead.ai/api/v1"


def _headers(config: dict) -> dict:
    return {"Content-Type": "application/json"}


def _params(config: dict) -> dict:
    return {"api_key": config.get("api_key", "")}


@register_node("smartlead.create_campaign")
async def smartlead_create_campaign(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/campaigns/create", params=_params(merged), json={
            "name": merged.get("name", ""),
            "client_id": merged.get("client_id"),
        })
        r.raise_for_status()
    return r.json()


@register_node("smartlead.add_leads")
async def smartlead_add_leads(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    campaign_id = merged.get("campaign_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/campaigns/{campaign_id}/leads", params=_params(merged), json={
            "lead_list": merged.get("leads", []),
        })
        r.raise_for_status()
    return r.json()


@register_node("smartlead.get_campaigns")
async def smartlead_get_campaigns(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/campaigns", params=_params(merged))
        r.raise_for_status()
    return {"campaigns": r.json()}
