"""Zoho Campaigns email marketing — handler for zoho_campaigns integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://campaigns.zoho.com/api/v1.1"


@register_node("zoho_campaigns.list_mailing_lists")
async def zoho_campaigns_list_mailing_lists(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List mailing lists.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/getmailinglists", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("zoho_campaigns.list_mailing_lists")
    return {"data": data}

@register_node("zoho_campaigns.add_subscriber")
async def zoho_campaigns_add_subscriber(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Add subscriber to list.

    config/input_data:
      api_key — API key or token (required)
      listkey — (required)
      contactinfo — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    listkey = merged.get("listkey") or ""
    contactinfo = merged.get("contactinfo") or ""
    if not listkey or not contactinfo:
        raise ValueError("listkey, contactinfo required for zoho_campaigns.add_subscriber")
    payload = {"listkey": listkey, "contactinfo": contactinfo}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/json/listsubscribe", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("zoho_campaigns.add_subscriber")
    return {"data": data}

@register_node("zoho_campaigns.list_campaigns")
async def zoho_campaigns_list_campaigns(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List recent campaigns.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/recentcampaigns", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("zoho_campaigns.list_campaigns")
    return {"data": data}
