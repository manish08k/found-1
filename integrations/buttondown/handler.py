"""Buttondown integration — newsletter platform via Buttondown API v1."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BUTTONDOWN_BASE = "https://api.buttondown.email/v1"


def _headers(config: dict, input_data: dict) -> dict:
    merged = {**config, **input_data}
    return {"Authorization": f"Token {merged.get('api_key', '')}"}


@register_node("buttondown.list_subscribers")
async def list_subscribers(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List subscribers from Buttondown.

    config/input_data:
      api_key — Buttondown API key (required)
    """
    headers = _headers(config, input_data)
    async with httpx.AsyncClient(base_url=BUTTONDOWN_BASE, timeout=30) as client:
        r = await client.get("/subscribers", params={"page": 1}, headers=headers)
        r.raise_for_status()
        data = r.json()
    results = data.get("results", [])
    log.info("buttondown.list_subscribers", count=len(results))
    return {"subscribers": results, "count": len(results), "total": data.get("count", len(results))}


@register_node("buttondown.create_subscriber")
async def create_subscriber(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new subscriber in Buttondown.

    config/input_data:
      api_key       — Buttondown API key (required)
      email_address — Subscriber email address (required)
    """
    merged = {**config, **input_data}
    email_address = merged.get("email_address", "") or merged.get("email", "")
    if not email_address:
        raise ValueError("email_address is required for buttondown.create_subscriber")
    headers = _headers(config, input_data)
    payload = {"email_address": email_address, "type": "regular"}
    async with httpx.AsyncClient(base_url=BUTTONDOWN_BASE, timeout=30) as client:
        r = await client.post("/subscribers", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("buttondown.create_subscriber", email_address=email_address)
    return {"subscriber": data, "email_address": email_address}


@register_node("buttondown.list_emails")
async def list_emails(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List sent emails/newsletters in Buttondown.

    config/input_data:
      api_key — Buttondown API key (required)
    """
    headers = _headers(config, input_data)
    async with httpx.AsyncClient(base_url=BUTTONDOWN_BASE, timeout=30) as client:
        r = await client.get("/emails", params={"page": 1}, headers=headers)
        r.raise_for_status()
        data = r.json()
    results = data.get("results", [])
    log.info("buttondown.list_emails", count=len(results))
    return {"emails": results, "count": len(results), "total": data.get("count", len(results))}


@register_node("buttondown.create_draft")
async def create_draft(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a draft email in Buttondown.

    config/input_data:
      api_key — Buttondown API key (required)
      subject — Email subject (required)
      body    — Email body content (required)
    """
    merged = {**config, **input_data}
    subject = merged.get("subject", "")
    body = merged.get("body", "")
    if not subject or not body:
        raise ValueError("subject and body are required for buttondown.create_draft")
    headers = _headers(config, input_data)
    payload = {"subject": subject, "body": body, "status": "draft"}
    async with httpx.AsyncClient(base_url=BUTTONDOWN_BASE, timeout=30) as client:
        r = await client.post("/emails", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("buttondown.create_draft", subject=subject)
    return {"draft": data, "subject": subject}
