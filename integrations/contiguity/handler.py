"""Contiguity communication APIs (SMS, email) — handler for contiguity integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.contiguity.co/v1"


@register_node("contiguity.send_sms")
async def contiguity_send_sms(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send an SMS.

    config/input_data:
      api_key — API key or token (required)
      to — (required)
      message — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    to = merged.get("to") or ""
    message = merged.get("message") or ""
    if not to or not message:
        raise ValueError("to, message required for contiguity.send_sms")
    payload = {"to": to, "message": message}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/send/text", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("contiguity.send_sms")
    return {"data": data}

@register_node("contiguity.send_email")
async def contiguity_send_email(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send an email.

    config/input_data:
      api_key — API key or token (required)
      to — (required)
      subject — (required)
      body — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    to = merged.get("to") or ""
    subject = merged.get("subject") or ""
    body = merged.get("body") or ""
    if not to or not subject or not body:
        raise ValueError("to, subject, body required for contiguity.send_email")
    payload = {"to": to, "subject": subject, "body": body}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/send/email", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("contiguity.send_email")
    return {"data": data}
