"""Instantly.ai email outreach integration — campaigns, analytics, and leads."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

INSTANTLY_BASE = "https://api.instantly.ai/api/v1"


@register_node("instantly_ai.list_campaigns")
async def instantly_list_campaigns(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List campaigns from Instantly.ai.

    config/input_data:
      api_key — Instantly.ai API key (required)
      limit   — number of campaigns to return (default 10)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    limit = int(merged.get("limit", 10))

    url = f"{INSTANTLY_BASE}/campaign/list"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, params={"api_key": api_key, "limit": limit})
        r.raise_for_status()
        data = r.json()

    campaigns = data if isinstance(data, list) else data.get("campaigns", data)
    log.info("instantly_ai.list_campaigns", count=len(campaigns) if isinstance(campaigns, list) else None)
    return {"campaigns": campaigns}


@register_node("instantly_ai.get_campaign_analytics")
async def instantly_get_campaign_analytics(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get analytics summary for an Instantly.ai campaign.

    config/input_data:
      api_key     — Instantly.ai API key (required)
      campaign_id — campaign ID (required)
      start_date  — start date in YYYY-MM-DD format (required)
      end_date    — end date in YYYY-MM-DD format (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    campaign_id = merged.get("campaign_id") or ""
    start_date = merged.get("start_date") or ""
    end_date = merged.get("end_date") or ""

    if not campaign_id:
        raise ValueError("campaign_id is required for instantly_ai.get_campaign_analytics")
    if not start_date:
        raise ValueError("start_date is required for instantly_ai.get_campaign_analytics")
    if not end_date:
        raise ValueError("end_date is required for instantly_ai.get_campaign_analytics")

    url = f"{INSTANTLY_BASE}/analytics/campaign/summary"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            url,
            params={
                "api_key": api_key,
                "campaign_id": campaign_id,
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        r.raise_for_status()
        data = r.json()

    log.info("instantly_ai.get_campaign_analytics", campaign_id=campaign_id)
    return {"analytics": data, "campaign_id": campaign_id}


@register_node("instantly_ai.add_lead")
async def instantly_add_lead(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Add a lead to an Instantly.ai campaign.

    config/input_data:
      api_key     — Instantly.ai API key (required)
      campaign_id — campaign ID (required)
      email       — lead email (required)
      first_name  — lead first name
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    campaign_id = merged.get("campaign_id") or ""
    email = merged.get("email") or ""
    fn = merged.get("first_name") or ""

    if not campaign_id:
        raise ValueError("campaign_id is required for instantly_ai.add_lead")
    if not email:
        raise ValueError("email is required for instantly_ai.add_lead")

    url = f"{INSTANTLY_BASE}/lead/add"
    payload = {
        "api_key": api_key,
        "campaign_id": campaign_id,
        "email": email,
        "first_name": fn,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()

    log.info("instantly_ai.add_lead", email=email, campaign_id=campaign_id)
    return {"result": data}
