"""Front — customer communication hub integration."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

FRONT_BASE = "https://api2.frontapp.com"


def _headers(config: dict) -> dict:
    api_key = config.get("api_key", "")
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


@register_node("front.list_conversations")
async def front_list_conversations(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List unassigned conversations from Front.

    config:
      api_key — Front API key
      limit   — number of conversations to return (default 25)
    """
    limit = int(config.get("limit", 25))

    async with httpx.AsyncClient(base_url=FRONT_BASE, timeout=30) as client:
        r = await client.get(
            "/conversations",
            params={"q[statuses][]": "unassigned", "limit": limit},
            headers=_headers(config),
        )
        r.raise_for_status()
        data = r.json()

    conversations = data.get("_results", data.get("conversations", []))
    log.info("front.list_conversations", count=len(conversations))
    return {
        "conversations": conversations,
        "count": len(conversations),
        "pagination": data.get("_pagination", {}),
    }


@register_node("front.get_conversation")
async def front_get_conversation(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single Front conversation by ID.

    config/input_data:
      api_key         — Front API key
      conversation_id — conversation ID (required)
    """
    conversation_id = config.get("conversation_id") or input_data.get("conversation_id")
    if not conversation_id:
        raise ValueError("conversation_id is required for front.get_conversation")

    async with httpx.AsyncClient(base_url=FRONT_BASE, timeout=30) as client:
        r = await client.get(
            f"/conversations/{conversation_id}",
            headers=_headers(config),
        )
        r.raise_for_status()
        conversation = r.json()

    log.info("front.get_conversation", conversation_id=conversation_id)
    return {"conversation": conversation, "conversation_id": conversation_id}


@register_node("front.send_message")
async def front_send_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a message via a Front channel.

    config/input_data:
      api_key    — Front API key
      channel_id — channel ID to send through (required)
      author_id  — sender author ID (required)
      email      — recipient email address (required)
      body       — message body text (required)
      subject    — message subject (optional)
    """
    channel_id = config.get("channel_id") or input_data.get("channel_id")
    author_id = config.get("author_id") or input_data.get("author_id")
    email = config.get("email") or input_data.get("email")
    body = config.get("body") or input_data.get("body")
    subject = config.get("subject") or input_data.get("subject", "")

    if not channel_id:
        raise ValueError("channel_id is required for front.send_message")
    if not author_id:
        raise ValueError("author_id is required for front.send_message")
    if not email:
        raise ValueError("email is required for front.send_message")
    if not body:
        raise ValueError("body is required for front.send_message")

    payload = {
        "author_id": author_id,
        "to": [email],
        "body": body,
        "subject": subject,
    }

    async with httpx.AsyncClient(base_url=FRONT_BASE, timeout=30) as client:
        r = await client.post(
            f"/channels/{channel_id}/messages",
            json=payload,
            headers=_headers(config),
        )
        r.raise_for_status()
        result = r.json()

    log.info("front.send_message", channel_id=channel_id, to=email)
    return {"message": result, "channel_id": channel_id, "to": email}


@register_node("front.list_contacts")
async def front_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts from Front.

    config:
      api_key — Front API key
      limit   — number of contacts to return (default 25)
    """
    limit = int(config.get("limit", 25))

    async with httpx.AsyncClient(base_url=FRONT_BASE, timeout=30) as client:
        r = await client.get(
            "/contacts",
            params={"limit": limit},
            headers=_headers(config),
        )
        r.raise_for_status()
        data = r.json()

    contacts = data.get("_results", data.get("contacts", []))
    log.info("front.list_contacts", count=len(contacts))
    return {
        "contacts": contacts,
        "count": len(contacts),
        "pagination": data.get("_pagination", {}),
    }
