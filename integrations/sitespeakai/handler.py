"""SiteSpeak AI chatbot integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://app.sitespeak.ai/api/v1"


@register_node("sitespeakai.create_chatbot")
async def sitespeakai_create_chatbot(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new SiteSpeak AI chatbot."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    payload = {
        "name": merged.get("name", ""),
        "url": merged.get("url", ""),
        "description": merged.get("description", ""),
        "language": merged.get("language", "en"),
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}/chatbots",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        result = r.json()
    log.info("sitespeakai.create_chatbot")
    return result


@register_node("sitespeakai.chat")
async def sitespeakai_chat(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a message to a SiteSpeak AI chatbot."""
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
        "message": message,
        "session_id": merged.get("session_id", ""),
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{BASE_URL}/chatbots/{chatbot_id}/chat",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        result = r.json()
    log.info("sitespeakai.chat")
    return result


@register_node("sitespeakai.list_chatbots")
async def sitespeakai_list_chatbots(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all SiteSpeak AI chatbots."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{BASE_URL}/chatbots",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        result = r.json()
    log.info("sitespeakai.list_chatbots")
    return result
