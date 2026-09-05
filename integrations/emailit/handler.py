"""EmailIt integration — transactional email via EmailIt API v1."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

EMAILIT_BASE = "https://api.emailit.com/v1"


def _headers(config: dict, input_data: dict) -> dict:
    merged = {**config, **input_data}
    return {"Authorization": f"Bearer {merged.get('api_key', '')}"}


@register_node("emailit.send_email")
async def send_email(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send an email via EmailIt.

    config/input_data:
      api_key    — EmailIt API key (required)
      from_email — Sender email address (required)
      to_email   — Recipient email address (required)
      subject    — Email subject (required)
      html       — HTML content (required)
    """
    merged = {**config, **input_data}
    from_email = merged.get("from_email", "") or merged.get("from", "")
    to_email = merged.get("to_email", "") or merged.get("to", "")
    subject = merged.get("subject", "")
    html = merged.get("html", "") or merged.get("body", "")
    if not from_email or not to_email or not subject:
        raise ValueError("from_email, to_email, and subject are required for emailit.send_email")
    headers = _headers(config, input_data)
    payload = {
        "from": from_email,
        "to": to_email,
        "subject": subject,
        "html": html,
    }
    async with httpx.AsyncClient(base_url=EMAILIT_BASE, timeout=30) as client:
        r = await client.post("/emails", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("emailit.send_email", to_email=to_email, subject=subject)
    return {"result": data, "to_email": to_email, "subject": subject}


@register_node("emailit.list_emails")
async def list_emails(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List sent emails in EmailIt.

    config/input_data:
      api_key — EmailIt API key (required)
    """
    headers = _headers(config, input_data)
    async with httpx.AsyncClient(base_url=EMAILIT_BASE, timeout=30) as client:
        r = await client.get("/emails", params={"limit": 25}, headers=headers)
        r.raise_for_status()
        data = r.json()
    emails = data.get("emails", data) if isinstance(data, dict) else data
    log.info("emailit.list_emails")
    return {"emails": emails}
