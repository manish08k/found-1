"""Chatwoot integration — customer messaging via Chatwoot API v1."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _client_and_headers(config: dict, input_data: dict):
    """Return (base_url, headers) for Chatwoot API calls."""
    merged = {**config, **input_data}
    base_url = merged.get("base_url", "").rstrip("/")
    account_id = merged.get("account_id", "")
    api_token = merged.get("api_token", "")
    if not base_url or not account_id:
        raise ValueError("base_url and account_id are required for Chatwoot")
    api_base = f"{base_url}/api/v1/accounts/{account_id}"
    headers = {"api_access_token": api_token}
    return api_base, headers


@register_node("chatwoot.list_conversations")
async def list_conversations(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List conversations from Chatwoot.

    config/input_data:
      base_url   — Chatwoot instance URL (required)
      account_id — Account ID (required)
      api_token  — API access token (required)
    """
    api_base, headers = _client_and_headers(config, input_data)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{api_base}/conversations", params={"page": 1}, headers=headers)
        r.raise_for_status()
        data = r.json()
    conversations = data.get("data", {}).get("payload", [])
    log.info("chatwoot.list_conversations", count=len(conversations))
    return {"conversations": conversations, "count": len(conversations)}


@register_node("chatwoot.get_conversation")
async def get_conversation(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a specific conversation from Chatwoot.

    config/input_data:
      base_url        — Chatwoot instance URL (required)
      account_id      — Account ID (required)
      api_token       — API access token (required)
      conversation_id — Conversation ID (required)
    """
    merged = {**config, **input_data}
    conversation_id = merged.get("conversation_id", "") or merged.get("id", "")
    if not conversation_id:
        raise ValueError("conversation_id is required for chatwoot.get_conversation")
    api_base, headers = _client_and_headers(config, input_data)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{api_base}/conversations/{conversation_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("chatwoot.get_conversation", conversation_id=conversation_id)
    return {"conversation": data, "conversation_id": conversation_id}


@register_node("chatwoot.create_conversation")
async def create_conversation(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new conversation in Chatwoot.

    config/input_data:
      base_url   — Chatwoot instance URL (required)
      account_id — Account ID (required)
      api_token  — API access token (required)
      inbox_id   — Inbox ID (required)
      contact_id — Contact ID (required)
    """
    merged = {**config, **input_data}
    inbox_id = merged.get("inbox_id", "")
    contact_id = merged.get("contact_id", "")
    if not inbox_id or not contact_id:
        raise ValueError("inbox_id and contact_id are required for chatwoot.create_conversation")
    api_base, headers = _client_and_headers(config, input_data)
    payload = {
        "inbox_id": inbox_id,
        "contact_id": contact_id,
        "additional_attributes": merged.get("additional_attributes", {}),
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{api_base}/conversations", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("chatwoot.create_conversation", inbox_id=inbox_id, contact_id=contact_id)
    return {"conversation": data, "inbox_id": inbox_id, "contact_id": contact_id}


@register_node("chatwoot.send_message")
async def send_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a message in a Chatwoot conversation.

    config/input_data:
      base_url        — Chatwoot instance URL (required)
      account_id      — Account ID (required)
      api_token       — API access token (required)
      conversation_id — Conversation ID (required)
      text            — Message content (required)
    """
    merged = {**config, **input_data}
    conversation_id = merged.get("conversation_id", "") or merged.get("id", "")
    text = merged.get("text", "") or merged.get("content", "")
    if not conversation_id or not text:
        raise ValueError("conversation_id and text are required for chatwoot.send_message")
    api_base, headers = _client_and_headers(config, input_data)
    payload = {"content": text, "message_type": "outgoing"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{api_base}/conversations/{conversation_id}/messages",
            json=payload,
            headers=headers,
        )
        r.raise_for_status()
        data = r.json()
    log.info("chatwoot.send_message", conversation_id=conversation_id)
    return {"message": data, "conversation_id": conversation_id}


@register_node("chatwoot.list_contacts")
async def list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts in Chatwoot.

    config/input_data:
      base_url   — Chatwoot instance URL (required)
      account_id — Account ID (required)
      api_token  — API access token (required)
    """
    api_base, headers = _client_and_headers(config, input_data)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{api_base}/contacts", params={"page": 1}, headers=headers)
        r.raise_for_status()
        data = r.json()
    contacts = data.get("payload", [])
    log.info("chatwoot.list_contacts", count=len(contacts))
    return {"contacts": contacts, "count": len(contacts)}
