"""Chatbase AI chatbot platform integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

CHATBASE_BASE = "https://www.chatbase.co/api/v1"


@register_node("chatbase.send_message")
async def chatbase_send_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a message to a Chatbase chatbot and get a response.

    config/input_data:
      api_key    — Chatbase API key
      chatbot_id — ID of the chatbot to message
      message    — user message to send
      conversation_id — optional, for continuing a conversation
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    chatbot_id = merged.get("chatbot_id", "")
    if not chatbot_id:
        raise ValueError("chatbot_id is required")
    message = merged.get("message", "")
    if not message:
        raise ValueError("message is required")

    payload = {
        "messages": [{"content": message, "role": "user"}],
        "chatbotId": chatbot_id,
        "stream": False,
        "temperature": merged.get("temperature", 0),
    }
    if merged.get("conversation_id"):
        payload["conversationId"] = merged["conversation_id"]

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{CHATBASE_BASE}/chat",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        result = r.json()

    log.info("chatbase.send_message", chatbot_id=chatbot_id)
    return result


@register_node("chatbase.list_chatbots")
async def chatbase_list_chatbots(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all chatbots in the Chatbase account.

    config/input_data:
      api_key — Chatbase API key
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{CHATBASE_BASE}/get-chatbots",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        result = r.json()

    log.info("chatbase.list_chatbots")
    return result


@register_node("chatbase.get_chatbot")
async def chatbase_get_chatbot(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details of a specific Chatbase chatbot.

    config/input_data:
      api_key    — Chatbase API key
      chatbot_id — ID of the chatbot to retrieve
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    chatbot_id = merged.get("chatbot_id", "")
    if not chatbot_id:
        raise ValueError("chatbot_id is required")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{CHATBASE_BASE}/get-chatbot",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"chatbotId": chatbot_id},
        )
        r.raise_for_status()
        result = r.json()

    log.info("chatbase.get_chatbot", chatbot_id=chatbot_id)
    return result


@register_node("chatbase.update_chatbot")
async def chatbase_update_chatbot(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update the settings of a Chatbase chatbot.

    config/input_data:
      api_key    — Chatbase API key
      chatbot_id — ID of the chatbot to update
      name       — optional new name
      instructions — optional new system instructions
      model      — optional model (e.g. gpt-4o, gpt-3.5-turbo)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    chatbot_id = merged.get("chatbot_id", "")
    if not chatbot_id:
        raise ValueError("chatbot_id is required")

    payload: dict = {"chatbotId": chatbot_id}
    for field in ("name", "instructions", "model", "temperature", "visibility"):
        if merged.get(field) is not None:
            payload[field] = merged[field]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{CHATBASE_BASE}/update-chatbot",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        result = r.json()

    log.info("chatbase.update_chatbot", chatbot_id=chatbot_id)
    return result
