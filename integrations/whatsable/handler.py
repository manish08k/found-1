"""WhatsAble WhatsApp business automation — handler for whatsable integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.whatsable.com/v1"


@register_node("whatsable.send_message")
async def whatsable_send_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a WhatsApp message.

    config/input_data:
      api_key — API key or token (required)
      to — (required)
      body — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    to = merged.get("to") or ""
    body = merged.get("body") or ""
    if not to or not body:
        raise ValueError("to, body required for whatsable.send_message")
    payload = {"to": to, "body": body}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/messages", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("whatsable.send_message")
    return {"data": data}

@register_node("whatsable.list_contacts")
async def whatsable_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
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
    log.info("whatsable.list_contacts")
    return {"data": data}

@register_node("whatsable.list_conversations")
async def whatsable_list_conversations(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List conversations.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/conversations", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("whatsable.list_conversations")
    return {"data": data}
