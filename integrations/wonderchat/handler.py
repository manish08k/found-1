"""Wonderchat — AI chatbot integration."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

WONDERCHAT_BASE = "https://wonderchat.io/api/v1"


def _headers(config: dict) -> dict:
    api_key = config.get("api_key", "")
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


@register_node("wonderchat.list_chatbots")
async def wonderchat_list_chatbots(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all AI chatbots from Wonderchat.

    config:
      api_key — Wonderchat API key
    """
    async with httpx.AsyncClient(base_url=WONDERCHAT_BASE, timeout=30) as client:
        r = await client.get("/chatbots", headers=_headers(config))
        r.raise_for_status()
        data = r.json()

    chatbots = data.get("chatbots", data if isinstance(data, list) else [])
    log.info("wonderchat.list_chatbots", count=len(chatbots))
    return {"chatbots": chatbots, "count": len(chatbots)}


@register_node("wonderchat.get_conversations")
async def wonderchat_get_conversations(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get conversations for a specific Wonderchat chatbot.

    config/input_data:
      api_key    — Wonderchat API key
      chatbot_id — chatbot ID to retrieve conversations for (required)
      limit      — number of conversations to return (default 25)
    """
    chatbot_id = config.get("chatbot_id") or input_data.get("chatbot_id")
    limit = int(config.get("limit", 25))

    if not chatbot_id:
        raise ValueError("chatbot_id is required for wonderchat.get_conversations")

    async with httpx.AsyncClient(base_url=WONDERCHAT_BASE, timeout=30) as client:
        r = await client.get(
            f"/chatbots/{chatbot_id}/conversations",
            params={"limit": limit},
            headers=_headers(config),
        )
        r.raise_for_status()
        data = r.json()

    conversations = data.get("conversations", data if isinstance(data, list) else [])
    log.info("wonderchat.get_conversations", chatbot_id=chatbot_id, count=len(conversations))
    return {"conversations": conversations, "count": len(conversations), "chatbot_id": chatbot_id}
