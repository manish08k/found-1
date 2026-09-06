"""Chatsistant AI assistant platform — handler for chatsistant integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.chatsistant.com/v1"


@register_node("chatsistant.send_message")
async def chatsistant_send_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a chat message.

    config/input_data:
      api_key — API key or token (required)
      message — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    message = merged.get("message") or ""
    if not message:
        raise ValueError("message required for chatsistant.send_message")
    payload = {"message": message}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/chat", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("chatsistant.send_message")
    return {"data": data}

@register_node("chatsistant.list_assistants")
async def chatsistant_list_assistants(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List assistants.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/assistants", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("chatsistant.list_assistants")
    return {"data": data}
