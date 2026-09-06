"""Chatfly AI chatbot builder — handler for chatfly integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.chatfly.co/v1"


@register_node("chatfly.list_bots")
async def chatfly_list_bots(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List chatbots.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/bots", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("chatfly.list_bots")
    return {"data": data}

@register_node("chatfly.send_message")
async def chatfly_send_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a message to a chatbot.

    config/input_data:
      api_key — API key or token (required)
      bot_id — (required)
      message — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    bot_id = merged.get("bot_id") or ""
    message = merged.get("message") or ""
    if not bot_id or not message:
        raise ValueError("bot_id, message required for chatfly.send_message")
    payload = {"message": message}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/bots/{bot_id}/chat", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("chatfly.send_message")
    return {"data": data}
