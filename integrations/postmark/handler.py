"""
Postmark email delivery integration.

Credential fields:
  - server_token: Postmark Server API Token (X-Postmark-Server-Token header)

Base URL: https://api.postmarkapp.com
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.postmarkapp.com"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    server_token = creds.get("server_token")
    if not server_token:
        raise ValueError("Postmark credential is missing 'server_token'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "X-Postmark-Server-Token": server_token,
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
        raise ValueError(f"Postmark API error {r.status_code}: {detail}")
    if not r.content:
        return {}
    return r.json()


# ---------------------------------------------------------------------------
# Email sending
# ---------------------------------------------------------------------------

@register_node("postmark.send_email")
async def postmark_send_email(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /email — send a single email."""
    to = config.get("To") if config.get("To") is not None else input_data.get("To")
    from_ = config.get("From") if config.get("From") is not None else input_data.get("From")
    subject = config.get("Subject") if config.get("Subject") is not None else input_data.get("Subject")
    if not to or not from_ or not subject:
        raise ValueError("postmark.send_email requires 'To', 'From', and 'Subject'")
    body: dict = {"To": to, "From": from_, "Subject": subject}
    text_body = config.get("TextBody") if config.get("TextBody") is not None else input_data.get("TextBody")
    if text_body is not None:
        body["TextBody"] = text_body
    html_body = config.get("HtmlBody") if config.get("HtmlBody") is not None else input_data.get("HtmlBody")
    if html_body is not None:
        body["HtmlBody"] = html_body
    cc = config.get("Cc") if config.get("Cc") is not None else input_data.get("Cc")
    if cc is not None:
        body["Cc"] = cc
    bcc = config.get("Bcc") if config.get("Bcc") is not None else input_data.get("Bcc")
    if bcc is not None:
        body["Bcc"] = bcc
    reply_to = config.get("ReplyTo") if config.get("ReplyTo") is not None else input_data.get("ReplyTo")
    if reply_to is not None:
        body["ReplyTo"] = reply_to
    message_stream = config.get("MessageStream") if config.get("MessageStream") is not None else input_data.get("MessageStream")
    if message_stream is not None:
        body["MessageStream"] = message_stream
    async with await _client(credential_id, db) as client:
        r = await client.post("/email", json=body)
    return _check(r)


@register_node("postmark.send_email_with_template")
async def postmark_send_email_with_template(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /email/withTemplate — send email using a saved template."""
    to = config.get("To") if config.get("To") is not None else input_data.get("To")
    from_ = config.get("From") if config.get("From") is not None else input_data.get("From")
    template_id = config.get("TemplateId") if config.get("TemplateId") is not None else input_data.get("TemplateId")
    template_alias = config.get("TemplateAlias") if config.get("TemplateAlias") is not None else input_data.get("TemplateAlias")
    if not to or not from_:
        raise ValueError("postmark.send_email_with_template requires 'To' and 'From'")
    if not template_id and not template_alias:
        raise ValueError("postmark.send_email_with_template requires 'TemplateId' or 'TemplateAlias'")
    body: dict = {"To": to, "From": from_}
    if template_id is not None:
        body["TemplateId"] = template_id
    if template_alias is not None:
        body["TemplateAlias"] = template_alias
    template_model = config.get("TemplateModel") if config.get("TemplateModel") is not None else input_data.get("TemplateModel")
    body["TemplateModel"] = template_model or {}
    message_stream = config.get("MessageStream") if config.get("MessageStream") is not None else input_data.get("MessageStream")
    if message_stream is not None:
        body["MessageStream"] = message_stream
    async with await _client(credential_id, db) as client:
        r = await client.post("/email/withTemplate", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Message history
# ---------------------------------------------------------------------------

@register_node("postmark.list_messages_outbound")
async def postmark_list_messages_outbound(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /messages/outbound — list outbound messages."""
    params: dict = {}
    count = config.get("count") if config.get("count") is not None else input_data.get("count")
    if count is not None:
        params["count"] = int(count)
    offset = config.get("offset") if config.get("offset") is not None else input_data.get("offset")
    if offset is not None:
        params["offset"] = int(offset)
    recipient = config.get("recipient") if config.get("recipient") is not None else input_data.get("recipient")
    if recipient is not None:
        params["recipient"] = recipient
    subject = config.get("subject") if config.get("subject") is not None else input_data.get("subject")
    if subject is not None:
        params["subject"] = subject
    async with await _client(credential_id, db) as client:
        r = await client.get("/messages/outbound", params=params)
    return _check(r)


@register_node("postmark.list_messages_inbound")
async def postmark_list_messages_inbound(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /messages/inbound — list inbound messages."""
    params: dict = {}
    count = config.get("count") if config.get("count") is not None else input_data.get("count")
    if count is not None:
        params["count"] = int(count)
    offset = config.get("offset") if config.get("offset") is not None else input_data.get("offset")
    if offset is not None:
        params["offset"] = int(offset)
    subject = config.get("subject") if config.get("subject") is not None else input_data.get("subject")
    if subject is not None:
        params["subject"] = subject
    mailbox_hash = config.get("mailboxhash") if config.get("mailboxhash") is not None else input_data.get("mailboxhash")
    if mailbox_hash is not None:
        params["mailboxhash"] = mailbox_hash
    async with await _client(credential_id, db) as client:
        r = await client.get("/messages/inbound", params=params)
    return _check(r)


@register_node("postmark.get_message_details")
async def postmark_get_message_details(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /messages/outbound/{messageid}/details — get full details for an outbound message."""
    message_id = config.get("message_id") if config.get("message_id") is not None else input_data.get("message_id")
    if not message_id:
        raise ValueError("postmark.get_message_details requires 'message_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/messages/outbound/{message_id}/details")
    return _check(r)


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

@register_node("postmark.create_template")
async def postmark_create_template(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /templates — create a new email template."""
    name = config.get("Name") if config.get("Name") is not None else input_data.get("Name")
    subject = config.get("Subject") if config.get("Subject") is not None else input_data.get("Subject")
    if not name or not subject:
        raise ValueError("postmark.create_template requires 'Name' and 'Subject'")
    body: dict = {"Name": name, "Subject": subject}
    text_body = config.get("TextBody") if config.get("TextBody") is not None else input_data.get("TextBody")
    if text_body is not None:
        body["TextBody"] = text_body
    html_body = config.get("HtmlBody") if config.get("HtmlBody") is not None else input_data.get("HtmlBody")
    if html_body is not None:
        body["HtmlBody"] = html_body
    alias = config.get("Alias") if config.get("Alias") is not None else input_data.get("Alias")
    if alias is not None:
        body["Alias"] = alias
    async with await _client(credential_id, db) as client:
        r = await client.post("/templates", json=body)
    return _check(r)


@register_node("postmark.list_templates")
async def postmark_list_templates(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /templates — list all templates."""
    params: dict = {}
    count = config.get("count") if config.get("count") is not None else input_data.get("count")
    if count is not None:
        params["count"] = int(count)
    offset = config.get("offset") if config.get("offset") is not None else input_data.get("offset")
    if offset is not None:
        params["offset"] = int(offset)
    async with await _client(credential_id, db) as client:
        r = await client.get("/templates", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Bounces
# ---------------------------------------------------------------------------

@register_node("postmark.list_bounces")
async def postmark_list_bounces(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /bounces — list bounced emails."""
    params: dict = {}
    count = config.get("count") if config.get("count") is not None else input_data.get("count")
    if count is not None:
        params["count"] = int(count)
    offset = config.get("offset") if config.get("offset") is not None else input_data.get("offset")
    if offset is not None:
        params["offset"] = int(offset)
    bounce_type = config.get("type") if config.get("type") is not None else input_data.get("type")
    if bounce_type is not None:
        params["type"] = bounce_type
    email_filter = config.get("emailFilter") if config.get("emailFilter") is not None else input_data.get("emailFilter")
    if email_filter is not None:
        params["emailFilter"] = email_filter
    async with await _client(credential_id, db) as client:
        r = await client.get("/bounces", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(creds: dict) -> None:
    """Test Postmark credentials by fetching server info."""
    server_token = creds.get("server_token")
    if not server_token:
        raise ValueError("Missing 'server_token'")
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "X-Postmark-Server-Token": server_token,
            "Accept": "application/json",
        },
        timeout=15.0,
    ) as client:
        r = await client.get("/server")
    if not r.is_success:
        raise ValueError(f"Postmark connection failed: {r.status_code} {r.text}")
