"""Zendesk Sell (Base CRM) sales platform — handler for zendesk_sell integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.getbase.com/v2"


@register_node("zendesk_sell.list_leads")
async def zendesk_sell_list_leads(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List leads.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/leads", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("zendesk_sell.list_leads")
    return {"data": data}

@register_node("zendesk_sell.create_lead")
async def zendesk_sell_create_lead(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a lead.

    config/input_data:
      api_key — API key or token (required)
      first_name — (required)
      last_name — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    first_name = merged.get("first_name") or ""
    last_name = merged.get("last_name") or ""
    if not first_name or not last_name:
        raise ValueError("first_name, last_name required for zendesk_sell.create_lead")
    payload = {"first_name": first_name, "last_name": last_name}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/leads", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("zendesk_sell.create_lead")
    return {"data": data}

@register_node("zendesk_sell.list_contacts")
async def zendesk_sell_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
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
    log.info("zendesk_sell.list_contacts")
    return {"data": data}

@register_node("zendesk_sell.create_contact")
async def zendesk_sell_create_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a contact.

    config/input_data:
      api_key — API key or token (required)
      first_name — (required)
      last_name — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    first_name = merged.get("first_name") or ""
    last_name = merged.get("last_name") or ""
    if not first_name or not last_name:
        raise ValueError("first_name, last_name required for zendesk_sell.create_contact")
    payload = {"first_name": first_name, "last_name": last_name}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/contacts", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("zendesk_sell.create_contact")
    return {"data": data}

@register_node("zendesk_sell.list_deals")
async def zendesk_sell_list_deals(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List deals.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/deals", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("zendesk_sell.list_deals")
    return {"data": data}

@register_node("zendesk_sell.create_deal")
async def zendesk_sell_create_deal(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a deal.

    config/input_data:
      api_key — API key or token (required)
      name — (required)
      contact_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    name = merged.get("name") or ""
    contact_id = merged.get("contact_id") or ""
    if not name or not contact_id:
        raise ValueError("name, contact_id required for zendesk_sell.create_deal")
    payload = {"name": name, "contact_id": contact_id}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/deals", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("zendesk_sell.create_deal")
    return {"data": data}
