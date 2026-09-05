"""ReachInbox email outreach integration — campaigns and leads."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

REACHINBOX_BASE = "https://api.reachinbox.ai/api/v1"


@register_node("reachinbox.list_campaigns")
async def reachinbox_list_campaigns(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List campaigns from ReachInbox.

    config/input_data:
      api_key — ReachInbox API key (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{REACHINBOX_BASE}/campaign"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()

    campaigns = data.get("data", data)
    log.info("reachinbox.list_campaigns", count=len(campaigns) if isinstance(campaigns, list) else None)
    return {"campaigns": campaigns}


@register_node("reachinbox.get_campaign")
async def reachinbox_get_campaign(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single ReachInbox campaign by ID.

    config/input_data:
      api_key — ReachInbox API key (required)
      id      — campaign ID (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    campaign_id = merged.get("id") or merged.get("campaign_id") or ""

    if not campaign_id:
        raise ValueError("id is required for reachinbox.get_campaign")

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{REACHINBOX_BASE}/campaign/{campaign_id}"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()

    campaign = data.get("data", data)
    log.info("reachinbox.get_campaign", campaign_id=campaign_id)
    return {"campaign": campaign}


@register_node("reachinbox.add_lead")
async def reachinbox_add_lead(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Add a lead to a ReachInbox campaign.

    config/input_data:
      api_key     — ReachInbox API key (required)
      campaign_id — campaign ID (required)
      email       — lead email (required)
      first_name  — lead first name
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    campaign_id = merged.get("campaign_id") or merged.get("id") or ""
    email = merged.get("email") or ""
    fn = merged.get("first_name") or ""

    if not campaign_id:
        raise ValueError("campaign_id is required for reachinbox.add_lead")
    if not email:
        raise ValueError("email is required for reachinbox.add_lead")

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{REACHINBOX_BASE}/campaign/{campaign_id}/leads"
    lead: dict = {"email": email}
    if fn:
        lead["firstName"] = fn
    payload = {"leads": [lead]}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    log.info("reachinbox.add_lead", campaign_id=campaign_id, email=email)
    return {"result": data}
