"""Lobstermail email marketing — handler for lobstermail integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.lobstermail.com/v1"


@register_node("lobstermail.send_email")
async def lobstermail_send_email(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send an email.

    config/input_data:
      api_key — API key or token (required)
      to — (required)
      subject — (required)
      body — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    to = merged.get("to") or ""
    subject = merged.get("subject") or ""
    body = merged.get("body") or ""
    if not to or not subject or not body:
        raise ValueError("to, subject, body required for lobstermail.send_email")
    payload = {"to": to, "subject": subject, "body": body}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/emails/send", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("lobstermail.send_email")
    return {"data": data}

@register_node("lobstermail.list_contacts")
async def lobstermail_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
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
    log.info("lobstermail.list_contacts")
    return {"data": data}

@register_node("lobstermail.create_contact")
async def lobstermail_create_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a contact.

    config/input_data:
      api_key — API key or token (required)
      email — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    email = merged.get("email") or ""
    if not email:
        raise ValueError("email required for lobstermail.create_contact")
    payload = {"email": email}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/contacts", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("lobstermail.create_contact")
    return {"data": data}
