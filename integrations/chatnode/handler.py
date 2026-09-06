"""ChatNode AI chatbot platform — handler for chatnode integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.chatnode.ai/v1"


@register_node("chatnode.send_message")
async def chatnode_send_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a chat message.

    config/input_data:
      api_key — API key or token (required)
      chatbot_id — (required)
      message — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    chatbot_id = merged.get("chatbot_id") or ""
    message = merged.get("message") or ""
    if not chatbot_id or not message:
        raise ValueError("chatbot_id, message required for chatnode.send_message")
    payload = {"chatbot_id": chatbot_id, "message": message}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/chat", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("chatnode.send_message")
    return {"data": data}

@register_node("chatnode.list_chatbots")
async def chatnode_list_chatbots(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List chatbots.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/chatbots", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("chatnode.list_chatbots")
    return {"data": data}

@register_node("chatnode.create_chatbot")
async def chatnode_create_chatbot(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a chatbot.

    config/input_data:
      api_key — API key or token (required)
      name — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    name = merged.get("name") or ""
    if not name:
        raise ValueError("name required for chatnode.create_chatbot")
    payload = {"name": name}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/chatbots", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("chatnode.create_chatbot")
    return {"data": data}
