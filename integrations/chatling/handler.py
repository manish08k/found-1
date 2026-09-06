"""Chatling AI chatbot builder integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

CHATLING_BASE = "https://api.chatling.ai/v1"


@register_node("chatling.send_message")
async def chatling_send_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a message to a Chatling bot.

    config/input_data:
      api_key  — Chatling API key
      bot_id   — ID of the bot to message
      message  — user message content
      session_id — optional session/conversation ID
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    bot_id = merged.get("bot_id", "")
    if not bot_id:
        raise ValueError("bot_id is required")
    message = merged.get("message", "")
    if not message:
        raise ValueError("message is required")

    payload: dict = {"message": message}
    if merged.get("session_id"):
        payload["session_id"] = merged["session_id"]

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{CHATLING_BASE}/bots/{bot_id}/chat",
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        result = r.json()

    log.info("chatling.send_message", bot_id=bot_id)
    return result


@register_node("chatling.list_bots")
async def chatling_list_bots(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all bots in a Chatling account.

    config/input_data:
      api_key — Chatling API key
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{CHATLING_BASE}/bots",
            headers={"x-api-key": api_key},
        )
        r.raise_for_status()
        result = r.json()

    log.info("chatling.list_bots")
    return result


@register_node("chatling.get_conversation")
async def chatling_get_conversation(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details of a Chatling conversation.

    config/input_data:
      api_key         — Chatling API key
      bot_id          — ID of the bot
      conversation_id — ID of the conversation to retrieve
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    bot_id = merged.get("bot_id", "")
    if not bot_id:
        raise ValueError("bot_id is required")
    conversation_id = merged.get("conversation_id", "")
    if not conversation_id:
        raise ValueError("conversation_id is required")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{CHATLING_BASE}/bots/{bot_id}/conversations/{conversation_id}",
            headers={"x-api-key": api_key},
        )
        r.raise_for_status()
        result = r.json()

    log.info("chatling.get_conversation", conversation_id=conversation_id)
    return result
