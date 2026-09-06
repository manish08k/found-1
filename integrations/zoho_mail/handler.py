"""Zoho Mail email service — handler for zoho_mail integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://mail.zoho.com/api"


@register_node("zoho_mail.list_folders")
async def zoho_mail_list_folders(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List mail folders.

    config/input_data:
      api_key — API key or token (required)
      account_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    account_id = merged.get("account_id") or ""
    if not account_id:
        raise ValueError("account_id required for zoho_mail.list_folders")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/accounts/{account_id}/folders", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("zoho_mail.list_folders")
    return {"data": data}

@register_node("zoho_mail.list_messages")
async def zoho_mail_list_messages(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List messages.

    config/input_data:
      api_key — API key or token (required)
      account_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    account_id = merged.get("account_id") or ""
    if not account_id:
        raise ValueError("account_id required for zoho_mail.list_messages")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/accounts/{account_id}/messages/view", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("zoho_mail.list_messages")
    return {"data": data}

@register_node("zoho_mail.send_message")
async def zoho_mail_send_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send an email.

    config/input_data:
      api_key — API key or token (required)
      account_id — (required)
      toAddress — (required)
      subject — (required)
      content — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    account_id = merged.get("account_id") or ""
    toAddress = merged.get("toAddress") or ""
    subject = merged.get("subject") or ""
    content = merged.get("content") or ""
    if not account_id or not toAddress or not subject or not content:
        raise ValueError("account_id, toAddress, subject, content required for zoho_mail.send_message")
    payload = {"toAddress": toAddress, "subject": subject, "content": content}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/accounts/{account_id}/messages", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("zoho_mail.send_message")
    return {"data": data}
