"""Bigin by Zoho CRM for small businesses — handler for bigin_by_zoho integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://www.zohoapis.com/bigin/v2"


@register_node("bigin_by_zoho.list_contacts")
async def bigin_by_zoho_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/Contacts", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("bigin_by_zoho.list_contacts")
    return {"data": data}

@register_node("bigin_by_zoho.create_contact")
async def bigin_by_zoho_create_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a contact.

    config/input_data:
      api_key — API key or token (required)
      Last_Name — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    Last_Name = merged.get("Last_Name") or ""
    if not Last_Name:
        raise ValueError("Last_Name required for bigin_by_zoho.create_contact")
    payload = {"Last_Name": Last_Name}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/Contacts", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("bigin_by_zoho.create_contact")
    return {"data": data}

@register_node("bigin_by_zoho.list_deals")
async def bigin_by_zoho_list_deals(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List deals.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/Deals", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("bigin_by_zoho.list_deals")
    return {"data": data}

@register_node("bigin_by_zoho.create_deal")
async def bigin_by_zoho_create_deal(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a deal.

    config/input_data:
      api_key — API key or token (required)
      Deal_Name — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    Deal_Name = merged.get("Deal_Name") or ""
    if not Deal_Name:
        raise ValueError("Deal_Name required for bigin_by_zoho.create_deal")
    payload = {"Deal_Name": Deal_Name}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/Deals", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("bigin_by_zoho.create_deal")
    return {"data": data}
