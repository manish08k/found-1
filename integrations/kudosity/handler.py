"""Kudosity SMS marketing platform — handler for kudosity integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.kudosity.com/v2"


@register_node("kudosity.send_sms")
async def kudosity_send_sms(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send an SMS.

    config/input_data:
      api_key — API key or token (required)
      to — (required)
      body — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    to = merged.get("to") or ""
    body = merged.get("body") or ""
    if not to or not body:
        raise ValueError("to, body required for kudosity.send_sms")
    payload = {"to": to, "body": body}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/sms/send", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("kudosity.send_sms")
    return {"data": data}

@register_node("kudosity.list_contacts")
async def kudosity_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/contacts", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("kudosity.list_contacts")
    return {"data": data}

@register_node("kudosity.create_contact")
async def kudosity_create_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a contact.

    config/input_data:
      api_key — API key or token (required)
      phone_number — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    phone_number = merged.get("phone_number") or ""
    if not phone_number:
        raise ValueError("phone_number required for kudosity.create_contact")
    payload = {"phone_number": phone_number}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/contacts", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("kudosity.create_contact")
    return {"data": data}
