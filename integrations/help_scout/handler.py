"""Help Scout (Activepieces variant) — handler for help_scout integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.helpscout.net/v2"


@register_node("help_scout.list_conversations")
async def help_scout_list_conversations(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List conversations.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/conversations", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("help_scout.list_conversations")
    return {"data": data}

@register_node("help_scout.create_conversation")
async def help_scout_create_conversation(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a conversation.

    config/input_data:
      api_key — API key or token (required)
      subject — (required)
      customer — (required)
      mailboxId — (required)
      type — (required)
      threads — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    subject = merged.get("subject") or ""
    customer = merged.get("customer") or ""
    mailboxId = merged.get("mailboxId") or ""
    type = merged.get("type") or ""
    threads = merged.get("threads") or ""
    if not subject or not customer or not mailboxId or not type or not threads:
        raise ValueError("subject, customer, mailboxId, type, threads required for help_scout.create_conversation")
    payload = {"subject": subject, "customer": customer, "mailboxId": mailboxId, "type": type, "threads": threads}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/conversations", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("help_scout.create_conversation")
    return {"data": data}

@register_node("help_scout.get_conversation")
async def help_scout_get_conversation(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get conversation details.

    config/input_data:
      api_key — API key or token (required)
      conversation_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    conversation_id = merged.get("conversation_id") or ""
    if not conversation_id:
        raise ValueError("conversation_id required for help_scout.get_conversation")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/conversations/{conversation_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("help_scout.get_conversation")
    return {"data": data}
