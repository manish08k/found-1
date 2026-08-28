"""
Email integration — sends via SendGrid's REST API. One of the most
commonly needed nodes in any automation tool ("email me when X happens"),
so it's worth having even before a broader integration catalog exists.

Credential fields: {"api_key": "SG...."}. SendGrid over raw SMTP because
a REST API call is simpler and more reliable to retry/observe than
managing an SMTP session inside a workflow node.
"""
import re
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

SENDGRID_BASE = "https://api.sendgrid.com/v3"

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email(addr: str, field_name: str) -> None:
    if not addr or not _EMAIL_RE.match(addr):
        raise ValueError(f"email.send: '{field_name}' is not a valid email address")


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Email credential is missing 'api_key'")
    return httpx.AsyncClient(
        base_url=SENDGRID_BASE,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )


@register_node("email.send")
async def email_send(config: dict, input_data: dict, credential_id: str, db) -> dict:
    to = config.get("to") or input_data.get("to")
    from_addr = config.get("from") or input_data.get("from")
    subject = config.get("subject") or input_data.get("subject", "")
    body = config.get("body") or input_data.get("body", "")
    is_html = bool(config.get("html", False))

    _validate_email(to, "to")
    _validate_email(from_addr, "from")
    if not subject:
        raise ValueError("email.send requires 'subject'")

    payload = {
        "personalizations": [{"to": [{"email": to}]}],
        "from": {"email": from_addr},
        "subject": subject,
        "content": [{"type": "text/html" if is_html else "text/plain", "value": body}],
    }

    async with await _client(credential_id, db) as client:
        r = await client.post("/mail/send", json=payload)
        r.raise_for_status()
        message_id = r.headers.get("X-Message-Id")

    return {"status_code": r.status_code, "message_id": message_id}


async def test_connection(creds: dict) -> None:
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Missing api_key")
    async with httpx.AsyncClient(base_url=SENDGRID_BASE, headers={"Authorization": f"Bearer {api_key}"}, timeout=10) as client:
        r = await client.get("/user/account")
        r.raise_for_status()
