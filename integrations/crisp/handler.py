"""Crisp integration — live chat platform via Crisp REST API v1."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

CRISP_BASE = "https://api.crisp.chat/v1"


def _auth_and_website(config: dict, input_data: dict) -> tuple:
    """Return (auth_tuple, website_id) for Crisp API calls."""
    merged = {**config, **input_data}
    identifier = merged.get("identifier", "")
    key = merged.get("key", "")
    website_id = merged.get("website_id", "")
    if not identifier or not key or not website_id:
        raise ValueError("identifier, key, and website_id are required for Crisp")
    return (identifier, key), website_id


@register_node("crisp.list_conversations")
async def list_conversations(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List conversations for a Crisp website.

    config/input_data:
      identifier — Crisp API identifier (required)
      key        — Crisp API key (required)
      website_id — Website ID (required)
    """
    auth, website_id = _auth_and_website(config, input_data)
    async with httpx.AsyncClient(base_url=CRISP_BASE, timeout=30) as client:
        r = await client.get(f"/website/{website_id}/conversations/1", auth=auth)
        r.raise_for_status()
        data = r.json()
    conversations = data.get("data", [])
    log.info("crisp.list_conversations", website_id=website_id, count=len(conversations))
    return {"conversations": conversations, "count": len(conversations), "website_id": website_id}


@register_node("crisp.send_message")
async def send_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a message in a Crisp conversation.

    config/input_data:
      identifier — Crisp API identifier (required)
      key        — Crisp API key (required)
      website_id — Website ID (required)
      session_id — Conversation session ID (required)
      text       — Message text (required)
    """
    merged = {**config, **input_data}
    auth, website_id = _auth_and_website(config, input_data)
    session_id = merged.get("session_id", "")
    text = merged.get("text", "") or merged.get("content", "")
    if not session_id or not text:
        raise ValueError("session_id and text are required for crisp.send_message")
    payload = {"type": "text", "from": "operator", "origin": "chat", "content": text}
    async with httpx.AsyncClient(base_url=CRISP_BASE, timeout=30) as client:
        r = await client.post(
            f"/website/{website_id}/conversation/{session_id}/message",
            json=payload,
            auth=auth,
        )
        r.raise_for_status()
        data = r.json()
    log.info("crisp.send_message", website_id=website_id, session_id=session_id)
    return {"result": data, "session_id": session_id, "website_id": website_id}


@register_node("crisp.list_contacts")
async def list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List people/contacts in a Crisp website.

    config/input_data:
      identifier — Crisp API identifier (required)
      key        — Crisp API key (required)
      website_id — Website ID (required)
    """
    auth, website_id = _auth_and_website(config, input_data)
    async with httpx.AsyncClient(base_url=CRISP_BASE, timeout=30) as client:
        r = await client.get(f"/website/{website_id}/people/list/segments/1", auth=auth)
        r.raise_for_status()
        data = r.json()
    contacts = data.get("data", [])
    log.info("crisp.list_contacts", website_id=website_id, count=len(contacts))
    return {"contacts": contacts, "count": len(contacts), "website_id": website_id}
