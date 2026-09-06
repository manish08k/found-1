"""Facebook Lead Ads (Activepieces variant) — handler for facebook_leads integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://graph.facebook.com/v18.0"


@register_node("facebook_leads.list_lead_forms")
async def facebook_leads_list_lead_forms(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List lead forms for a page.

    config/input_data:
      api_key — API key or token (required)
      page_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    page_id = merged.get("page_id") or ""
    if not page_id:
        raise ValueError("page_id required for facebook_leads.list_lead_forms")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/{page_id}/leadgen_forms", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("facebook_leads.list_lead_forms")
    return {"data": data}

@register_node("facebook_leads.get_leads")
async def facebook_leads_get_leads(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get leads from a form.

    config/input_data:
      api_key — API key or token (required)
      form_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    form_id = merged.get("form_id") or ""
    if not form_id:
        raise ValueError("form_id required for facebook_leads.get_leads")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/{form_id}/leads", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("facebook_leads.get_leads")
    return {"data": data}
