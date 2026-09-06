"""WhatsScale WhatsApp marketing platform — handler for whatsscale integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.whatsscale.com/v1"


@register_node("whatsscale.send_message")
async def whatsscale_send_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a message.

    config/input_data:
      api_key — API key or token (required)
      to — (required)
      template_name — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    to = merged.get("to") or ""
    template_name = merged.get("template_name") or ""
    if not to or not template_name:
        raise ValueError("to, template_name required for whatsscale.send_message")
    payload = {"to": to, "template_name": template_name}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/messages", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("whatsscale.send_message")
    return {"data": data}

@register_node("whatsscale.list_templates")
async def whatsscale_list_templates(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List message templates.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/templates", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("whatsscale.list_templates")
    return {"data": data}

@register_node("whatsscale.list_contacts")
async def whatsscale_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
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
    log.info("whatsscale.list_contacts")
    return {"data": data}
