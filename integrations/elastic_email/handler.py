"""Elastic Email integration — transactional and marketing email via Elastic Email API v4."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

ELASTIC_EMAIL_BASE = "https://api.elasticemail.com/v4"


def _headers(config: dict, input_data: dict) -> dict:
    merged = {**config, **input_data}
    return {"X-ElasticEmail-ApiKey": merged.get("api_key", "")}


@register_node("elastic_email.send_email")
async def send_email(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send an email via Elastic Email.

    config/input_data:
      api_key    — Elastic Email API key (required)
      to_email   — Recipient email address (required)
      from_email — Sender email address (required)
      subject    — Email subject (required)
      body       — HTML body content (required)
    """
    merged = {**config, **input_data}
    to_email = merged.get("to_email", "") or merged.get("to", "")
    from_email = merged.get("from_email", "") or merged.get("from", "")
    subject = merged.get("subject", "")
    body = merged.get("body", "") or merged.get("html", "")
    if not to_email or not from_email or not subject:
        raise ValueError("to_email, from_email, and subject are required for elastic_email.send_email")
    headers = _headers(config, input_data)
    payload = {
        "Recipients": {"To": [to_email]},
        "Content": {
            "From": from_email,
            "Subject": subject,
            "Body": [{"ContentType": "HTML", "Content": body}],
        },
    }
    async with httpx.AsyncClient(base_url=ELASTIC_EMAIL_BASE, timeout=30) as client:
        r = await client.post("/emails", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("elastic_email.send_email", to_email=to_email, subject=subject)
    return {"result": data, "to_email": to_email, "subject": subject}


@register_node("elastic_email.list_contacts")
async def list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts in Elastic Email.

    config/input_data:
      api_key — Elastic Email API key (required)
    """
    headers = _headers(config, input_data)
    async with httpx.AsyncClient(base_url=ELASTIC_EMAIL_BASE, timeout=30) as client:
        r = await client.get("/contacts", params={"limit": 25, "offset": 0}, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("elastic_email.list_contacts", count=len(data) if isinstance(data, list) else 1)
    return {"contacts": data}


@register_node("elastic_email.add_contact")
async def add_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Add a contact to Elastic Email.

    config/input_data:
      api_key    — Elastic Email API key (required)
      email      — Contact email address (required)
      first_name — Contact first name (optional)
    """
    merged = {**config, **input_data}
    email = merged.get("email", "")
    first_name = merged.get("first_name", "")
    if not email:
        raise ValueError("email is required for elastic_email.add_contact")
    headers = _headers(config, input_data)
    payload = [{"Email": email, "FirstName": first_name}]
    async with httpx.AsyncClient(base_url=ELASTIC_EMAIL_BASE, timeout=30) as client:
        r = await client.post("/contacts", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("elastic_email.add_contact", email=email)
    return {"result": data, "email": email}
