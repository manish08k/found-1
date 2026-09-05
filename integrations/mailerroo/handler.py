"""Mailerroo integration — transactional email via Mailerroo API v1."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

MAILERROO_BASE = "https://api.mailerroo.com/v1"


def _headers(config: dict, input_data: dict) -> dict:
    merged = {**config, **input_data}
    return {"Authorization": f"Bearer {merged.get('api_key', '')}"}


@register_node("mailerroo.send_email")
async def send_email(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a transactional email via Mailerroo.

    config/input_data:
      api_key    — Mailerroo API key (required)
      from_email — Sender email address (required)
      to_email   — Recipient email address (required)
      subject    — Email subject (required)
      html_body  — HTML body content (required)
    """
    merged = {**config, **input_data}
    from_email = merged.get("from_email", "") or merged.get("from", "")
    to_email = merged.get("to_email", "") or merged.get("to", "")
    subject = merged.get("subject", "")
    html_body = merged.get("html_body", "") or merged.get("html", "")
    if not from_email or not to_email or not subject:
        raise ValueError("from_email, to_email, and subject are required for mailerroo.send_email")
    headers = _headers(config, input_data)
    payload = {
        "from": from_email,
        "to": to_email,
        "subject": subject,
        "html": html_body,
    }
    async with httpx.AsyncClient(base_url=MAILERROO_BASE, timeout=30) as client:
        r = await client.post("/send", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("mailerroo.send_email", to_email=to_email, subject=subject)
    return {"result": data, "to_email": to_email, "subject": subject}


@register_node("mailerroo.list_templates")
async def list_templates(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all email templates in Mailerroo.

    config/input_data:
      api_key — Mailerroo API key (required)
    """
    headers = _headers(config, input_data)
    async with httpx.AsyncClient(base_url=MAILERROO_BASE, timeout=30) as client:
        r = await client.get("/templates", headers=headers)
        r.raise_for_status()
        data = r.json()
    templates = data.get("templates", data) if isinstance(data, dict) else data
    log.info("mailerroo.list_templates")
    return {"templates": templates}
