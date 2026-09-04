"""
Resend email delivery integration.

Credential fields:
  - api_key: Resend API key (sent as Authorization: Bearer header)

Base URL: https://api.resend.com
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.resend.com"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Resend credential is missing 'api_key'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Resend API error {r.status_code}: {detail}")
    if not r.content:
        return {}
    return r.json()


# ---------------------------------------------------------------------------
# Emails
# ---------------------------------------------------------------------------

@register_node("resend.send_email")
async def resend_send_email(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /emails — send an email via Resend."""
    to = config.get("to") if config.get("to") is not None else input_data.get("to")
    from_ = config.get("from") if config.get("from") is not None else input_data.get("from")
    subject = config.get("subject") if config.get("subject") is not None else input_data.get("subject")
    if not to or not from_ or not subject:
        raise ValueError("resend.send_email requires 'to', 'from', and 'subject'")
    body: dict = {
        "to": to if isinstance(to, list) else [to],
        "from": from_,
        "subject": subject,
    }
    html = config.get("html") if config.get("html") is not None else input_data.get("html")
    if html is not None:
        body["html"] = html
    text = config.get("text") if config.get("text") is not None else input_data.get("text")
    if text is not None:
        body["text"] = text
    cc = config.get("cc") if config.get("cc") is not None else input_data.get("cc")
    if cc is not None:
        body["cc"] = cc if isinstance(cc, list) else [cc]
    bcc = config.get("bcc") if config.get("bcc") is not None else input_data.get("bcc")
    if bcc is not None:
        body["bcc"] = bcc if isinstance(bcc, list) else [bcc]
    reply_to = config.get("reply_to") if config.get("reply_to") is not None else input_data.get("reply_to")
    if reply_to is not None:
        body["reply_to"] = reply_to
    tags = config.get("tags") if config.get("tags") is not None else input_data.get("tags")
    if tags is not None:
        body["tags"] = tags
    async with await _client(credential_id, db) as client:
        r = await client.post("/emails", json=body)
    return _check(r)


@register_node("resend.get_email")
async def resend_get_email(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /emails/{id} — retrieve an email by ID."""
    email_id = config.get("email_id") if config.get("email_id") is not None else input_data.get("email_id")
    if not email_id:
        raise ValueError("resend.get_email requires 'email_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/emails/{email_id}")
    return _check(r)


@register_node("resend.cancel_email")
async def resend_cancel_email(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /emails/{id}/cancel — cancel a scheduled email."""
    email_id = config.get("email_id") if config.get("email_id") is not None else input_data.get("email_id")
    if not email_id:
        raise ValueError("resend.cancel_email requires 'email_id'")
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/emails/{email_id}/cancel")
    return _check(r)


# ---------------------------------------------------------------------------
# Domains
# ---------------------------------------------------------------------------

@register_node("resend.create_domain")
async def resend_create_domain(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /domains — add a new sending domain."""
    name = config.get("name") if config.get("name") is not None else input_data.get("name")
    if not name:
        raise ValueError("resend.create_domain requires 'name'")
    body: dict = {"name": name}
    region = config.get("region") if config.get("region") is not None else input_data.get("region")
    if region is not None:
        body["region"] = region
    async with await _client(credential_id, db) as client:
        r = await client.post("/domains", json=body)
    return _check(r)


@register_node("resend.list_domains")
async def resend_list_domains(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /domains — list all sending domains."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/domains")
    return _check(r)


@register_node("resend.verify_domain")
async def resend_verify_domain(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /domains/{id}/verify — trigger domain verification."""
    domain_id = config.get("domain_id") if config.get("domain_id") is not None else input_data.get("domain_id")
    if not domain_id:
        raise ValueError("resend.verify_domain requires 'domain_id'")
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/domains/{domain_id}/verify")
    return _check(r)


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------

@register_node("resend.list_api_keys")
async def resend_list_api_keys(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /api-keys — list all API keys for the account."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/api-keys")
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(creds: dict) -> None:
    """Test Resend credentials by listing domains."""
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Missing 'api_key'")
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        timeout=15.0,
    ) as client:
        r = await client.get("/domains")
    if not r.is_success:
        raise ValueError(f"Resend connection failed: {r.status_code} {r.text}")
