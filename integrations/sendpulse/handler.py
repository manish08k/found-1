"""SendPulse integration — multi-channel marketing via SendPulse API."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

SENDPULSE_BASE = "https://api.sendpulse.com"


async def _get_access_token(config: dict, input_data: dict) -> str:
    """Obtain an OAuth2 access token using client credentials."""
    merged = {**config, **input_data}
    client_id = merged.get("client_id", "")
    client_secret = merged.get("client_secret", "")
    if not client_id or not client_secret:
        raise ValueError("client_id and client_secret are required for SendPulse")
    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }
    async with httpx.AsyncClient(base_url=SENDPULSE_BASE, timeout=30) as client:
        r = await client.post("/oauth/access_token", json=payload)
        r.raise_for_status()
        token_data = r.json()
    access_token = token_data.get("access_token", "")
    if not access_token:
        raise ValueError("Failed to obtain SendPulse access token")
    return access_token


@register_node("sendpulse.list_mailing_lists")
async def list_mailing_lists(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all mailing lists (address books) in SendPulse.

    config/input_data:
      client_id     — SendPulse client ID (required)
      client_secret — SendPulse client secret (required)
    """
    token = await _get_access_token(config, input_data)
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(base_url=SENDPULSE_BASE, timeout=30) as client:
        r = await client.get("/addressbooks", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("sendpulse.list_mailing_lists", count=len(data) if isinstance(data, list) else 1)
    return {"mailing_lists": data}


@register_node("sendpulse.add_emails")
async def add_emails(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Add emails to an address book in SendPulse.

    config/input_data:
      client_id     — SendPulse client ID (required)
      client_secret — SendPulse client secret (required)
      address_book_id — Address book ID (required)
      email           — Email to add (required)
    """
    merged = {**config, **input_data}
    address_book_id = merged.get("address_book_id", "")
    email = merged.get("email", "")
    if not address_book_id or not email:
        raise ValueError("address_book_id and email are required for sendpulse.add_emails")
    token = await _get_access_token(config, input_data)
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"emails": [{"email": email, "variables": merged.get("variables", {})}]}
    async with httpx.AsyncClient(base_url=SENDPULSE_BASE, timeout=30) as client:
        r = await client.post(f"/addressbooks/{address_book_id}/emails", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("sendpulse.add_emails", address_book_id=address_book_id, email=email)
    return {"result": data, "email": email, "address_book_id": address_book_id}


@register_node("sendpulse.send_email")
async def send_email(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a transactional email via SendPulse SMTP.

    config/input_data:
      client_id     — SendPulse client ID (required)
      client_secret — SendPulse client secret (required)
      from_name     — Sender name (required)
      from_email    — Sender email (required)
      to_email      — Recipient email (required)
      to_name       — Recipient name (optional)
      subject       — Email subject (required)
      body          — Email body text (required)
    """
    merged = {**config, **input_data}
    from_email = merged.get("from_email", "")
    from_name = merged.get("from_name", "")
    to_email = merged.get("to_email", "")
    to_name = merged.get("to_name", "")
    subject = merged.get("subject", "")
    body = merged.get("body", "")
    if not from_email or not to_email or not subject:
        raise ValueError("from_email, to_email, and subject are required for sendpulse.send_email")
    token = await _get_access_token(config, input_data)
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "email": {
            "from": {"name": from_name, "email": from_email},
            "to": [{"name": to_name, "email": to_email}],
            "subject": subject,
            "text": body,
        }
    }
    async with httpx.AsyncClient(base_url=SENDPULSE_BASE, timeout=30) as client:
        r = await client.post("/smtp/emails", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("sendpulse.send_email", to_email=to_email, subject=subject)
    return {"result": data, "to_email": to_email, "subject": subject}
