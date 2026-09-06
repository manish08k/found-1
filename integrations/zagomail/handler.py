"""Zagomail email marketing platform — handler for zagomail integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.zagomail.com/v1"


@register_node("zagomail.list_contacts")
async def zagomail_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/contacts", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("zagomail.list_contacts")
    return {"data": data}

@register_node("zagomail.add_contact")
async def zagomail_add_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Add a contact.

    config/input_data:
      api_key — API key or token (required)
      email — (required)
      list_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    email = merged.get("email") or ""
    list_id = merged.get("list_id") or ""
    if not email or not list_id:
        raise ValueError("email, list_id required for zagomail.add_contact")
    payload = {"email": email, "list_id": list_id}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/contacts", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("zagomail.add_contact")
    return {"data": data}

@register_node("zagomail.list_campaigns")
async def zagomail_list_campaigns(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List campaigns.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/campaigns", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("zagomail.list_campaigns")
    return {"data": data}

@register_node("zagomail.send_campaign")
async def zagomail_send_campaign(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a campaign.

    config/input_data:
      api_key — API key or token (required)
      campaign_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    campaign_id = merged.get("campaign_id") or ""
    if not campaign_id:
        raise ValueError("campaign_id required for zagomail.send_campaign")
    payload = merged
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/campaigns/{campaign_id}/send", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("zagomail.send_campaign")
    return {"data": data}
