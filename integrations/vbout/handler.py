"""VBOUT marketing automation — handler for vbout integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.vbout.com/1"


@register_node("vbout.list_contacts")
async def vbout_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Content-Type": "application/json"}
    # Auth passed as query param: api_key
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/app/contacts/getall.json", headers=headers, params={"api_key": api_key})
        r.raise_for_status()
        data = r.json()
    log.info("vbout.list_contacts")
    return {"data": data}

@register_node("vbout.add_contact")
async def vbout_add_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Add a contact.

    config/input_data:
      api_key — API key or token (required)
      email — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Content-Type": "application/json"}
    # Auth passed as query param: api_key
    email = merged.get("email") or ""
    if not email:
        raise ValueError("email required for vbout.add_contact")
    payload = {"email": email}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/app/contacts/addcontact.json", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("vbout.add_contact")
    return {"data": data}

@register_node("vbout.send_email")
async def vbout_send_email(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send an email campaign.

    config/input_data:
      api_key — API key or token (required)
      campaign_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Content-Type": "application/json"}
    # Auth passed as query param: api_key
    campaign_id = merged.get("campaign_id") or ""
    if not campaign_id:
        raise ValueError("campaign_id required for vbout.send_email")
    payload = {"campaign_id": campaign_id}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/emailmarketing/send.json", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("vbout.send_email")
    return {"data": data}
