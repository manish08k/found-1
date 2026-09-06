"""Gmail email service (Google) — handler for gmail integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://gmail.googleapis.com/gmail/v1"


@register_node("gmail.list_messages")
async def gmail_list_messages(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List email messages.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/users/me/messages", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("gmail.list_messages")
    return {"data": data}

@register_node("gmail.get_message")
async def gmail_get_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get an email message.

    config/input_data:
      api_key — API key or token (required)
      message_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    message_id = merged.get("message_id") or ""
    if not message_id:
        raise ValueError("message_id required for gmail.get_message")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/users/me/messages/{message_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("gmail.get_message")
    return {"data": data}

@register_node("gmail.send_message")
async def gmail_send_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send an email.

    config/input_data:
      api_key — API key or token (required)
      raw — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    raw = merged.get("raw") or ""
    if not raw:
        raise ValueError("raw required for gmail.send_message")
    payload = {"raw": raw}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/users/me/messages/send", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("gmail.send_message")
    return {"data": data}

@register_node("gmail.list_labels")
async def gmail_list_labels(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List labels.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/users/me/labels", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("gmail.list_labels")
    return {"data": data}
