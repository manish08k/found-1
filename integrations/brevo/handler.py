"""
Brevo (formerly Sendinblue) email & marketing integration.

Credential fields:
  - api_key: Brevo API key (sent as 'api-key' header)

Base URL: https://api.brevo.com/v3
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.brevo.com/v3"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Brevo credential is missing 'api_key'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "api-key": api_key,
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
        raise ValueError(f"Brevo API error {r.status_code}: {detail}")
    if not r.content:
        return {}
    return r.json()


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

@register_node("brevo.send_email")
async def brevo_send_email(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /smtp/email — send a transactional email (simple form)."""
    to = config.get("to") if config.get("to") is not None else input_data.get("to")
    sender = config.get("sender") if config.get("sender") is not None else input_data.get("sender")
    subject = config.get("subject") if config.get("subject") is not None else input_data.get("subject")
    if not to or not sender or not subject:
        raise ValueError("brevo.send_email requires 'to', 'sender', and 'subject'")
    body: dict = {"to": to, "sender": sender, "subject": subject}
    html_content = config.get("htmlContent") if config.get("htmlContent") is not None else input_data.get("htmlContent")
    if html_content is not None:
        body["htmlContent"] = html_content
    text_content = config.get("textContent") if config.get("textContent") is not None else input_data.get("textContent")
    if text_content is not None:
        body["textContent"] = text_content
    cc = config.get("cc") if config.get("cc") is not None else input_data.get("cc")
    if cc is not None:
        body["cc"] = cc
    bcc = config.get("bcc") if config.get("bcc") is not None else input_data.get("bcc")
    if bcc is not None:
        body["bcc"] = bcc
    async with await _client(credential_id, db) as client:
        r = await client.post("/smtp/email", json=body)
    return _check(r)


@register_node("brevo.send_transactional_email")
async def brevo_send_transactional_email(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /smtp/email — send transactional email with template support."""
    to = config.get("to") if config.get("to") is not None else input_data.get("to")
    sender = config.get("sender") if config.get("sender") is not None else input_data.get("sender")
    if not to or not sender:
        raise ValueError("brevo.send_transactional_email requires 'to' and 'sender'")
    body: dict = {"to": to, "sender": sender}
    template_id = config.get("templateId") if config.get("templateId") is not None else input_data.get("templateId")
    if template_id is not None:
        body["templateId"] = int(template_id)
    params_data = config.get("params") if config.get("params") is not None else input_data.get("params")
    if params_data is not None:
        body["params"] = params_data
    subject = config.get("subject") if config.get("subject") is not None else input_data.get("subject")
    if subject is not None:
        body["subject"] = subject
    html_content = config.get("htmlContent") if config.get("htmlContent") is not None else input_data.get("htmlContent")
    if html_content is not None:
        body["htmlContent"] = html_content
    text_content = config.get("textContent") if config.get("textContent") is not None else input_data.get("textContent")
    if text_content is not None:
        body["textContent"] = text_content
    async with await _client(credential_id, db) as client:
        r = await client.post("/smtp/email", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

@register_node("brevo.create_contact")
async def brevo_create_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /contacts — create a new contact."""
    email = config.get("email") if config.get("email") is not None else input_data.get("email")
    if not email:
        raise ValueError("brevo.create_contact requires 'email'")
    body: dict = {"email": email}
    attributes = config.get("attributes") if config.get("attributes") is not None else input_data.get("attributes")
    if attributes is not None:
        body["attributes"] = attributes
    list_ids = config.get("listIds") if config.get("listIds") is not None else input_data.get("listIds")
    if list_ids is not None:
        body["listIds"] = list_ids
    update_enabled = config.get("updateEnabled") if config.get("updateEnabled") is not None else input_data.get("updateEnabled")
    if update_enabled is not None:
        body["updateEnabled"] = bool(update_enabled)
    async with await _client(credential_id, db) as client:
        r = await client.post("/contacts", json=body)
    return _check(r)


@register_node("brevo.get_contact")
async def brevo_get_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /contacts/{identifier} — get contact by email or ID."""
    identifier = config.get("identifier") if config.get("identifier") is not None else input_data.get("identifier")
    if not identifier:
        raise ValueError("brevo.get_contact requires 'identifier' (email or contact ID)")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/contacts/{identifier}")
    return _check(r)


@register_node("brevo.update_contact")
async def brevo_update_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /contacts/{identifier} — update contact attributes or list membership."""
    identifier = config.get("identifier") if config.get("identifier") is not None else input_data.get("identifier")
    if not identifier:
        raise ValueError("brevo.update_contact requires 'identifier'")
    body: dict = {}
    attributes = config.get("attributes") if config.get("attributes") is not None else input_data.get("attributes")
    if attributes is not None:
        body["attributes"] = attributes
    list_ids = config.get("listIds") if config.get("listIds") is not None else input_data.get("listIds")
    if list_ids is not None:
        body["listIds"] = list_ids
    unlink_list_ids = config.get("unlinkListIds") if config.get("unlinkListIds") is not None else input_data.get("unlinkListIds")
    if unlink_list_ids is not None:
        body["unlinkListIds"] = unlink_list_ids
    async with await _client(credential_id, db) as client:
        r = await client.put(f"/contacts/{identifier}", json=body)
    return _check(r)


@register_node("brevo.delete_contact")
async def brevo_delete_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /contacts/{identifier} — delete a contact."""
    identifier = config.get("identifier") if config.get("identifier") is not None else input_data.get("identifier")
    if not identifier:
        raise ValueError("brevo.delete_contact requires 'identifier'")
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/contacts/{identifier}")
    return _check(r)


@register_node("brevo.list_contacts")
async def brevo_list_contacts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /contacts — list contacts with optional filters."""
    params: dict = {}
    limit = config.get("limit") if config.get("limit") is not None else input_data.get("limit")
    if limit is not None:
        params["limit"] = int(limit)
    offset = config.get("offset") if config.get("offset") is not None else input_data.get("offset")
    if offset is not None:
        params["offset"] = int(offset)
    modified_since = config.get("modifiedSince") if config.get("modifiedSince") is not None else input_data.get("modifiedSince")
    if modified_since is not None:
        params["modifiedSince"] = modified_since
    async with await _client(credential_id, db) as client:
        r = await client.get("/contacts", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------

@register_node("brevo.create_campaign")
async def brevo_create_campaign(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /emailCampaigns — create an email campaign."""
    name = config.get("name") if config.get("name") is not None else input_data.get("name")
    subject = config.get("subject") if config.get("subject") is not None else input_data.get("subject")
    sender = config.get("sender") if config.get("sender") is not None else input_data.get("sender")
    recipients = config.get("recipients") if config.get("recipients") is not None else input_data.get("recipients")
    if not name or not subject or not sender or not recipients:
        raise ValueError("brevo.create_campaign requires 'name', 'subject', 'sender', and 'recipients'")
    body: dict = {"name": name, "subject": subject, "sender": sender, "recipients": recipients}
    html_content = config.get("htmlContent") if config.get("htmlContent") is not None else input_data.get("htmlContent")
    if html_content is not None:
        body["htmlContent"] = html_content
    template_id = config.get("templateId") if config.get("templateId") is not None else input_data.get("templateId")
    if template_id is not None:
        body["templateId"] = int(template_id)
    scheduled_at = config.get("scheduledAt") if config.get("scheduledAt") is not None else input_data.get("scheduledAt")
    if scheduled_at is not None:
        body["scheduledAt"] = scheduled_at
    async with await _client(credential_id, db) as client:
        r = await client.post("/emailCampaigns", json=body)
    return _check(r)


@register_node("brevo.send_campaign")
async def brevo_send_campaign(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /emailCampaigns/{campaignId}/sendNow — send a campaign immediately."""
    campaign_id = config.get("campaignId") if config.get("campaignId") is not None else input_data.get("campaignId")
    if not campaign_id:
        raise ValueError("brevo.send_campaign requires 'campaignId'")
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/emailCampaigns/{campaign_id}/sendNow")
    return _check(r)


@register_node("brevo.list_campaigns")
async def brevo_list_campaigns(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /emailCampaigns — list email campaigns."""
    params: dict = {}
    status = config.get("status") if config.get("status") is not None else input_data.get("status")
    if status is not None:
        params["status"] = status
    limit = config.get("limit") if config.get("limit") is not None else input_data.get("limit")
    if limit is not None:
        params["limit"] = int(limit)
    offset = config.get("offset") if config.get("offset") is not None else input_data.get("offset")
    if offset is not None:
        params["offset"] = int(offset)
    async with await _client(credential_id, db) as client:
        r = await client.get("/emailCampaigns", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(creds: dict) -> None:
    """Test Brevo credentials by fetching account info."""
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Missing 'api_key'")
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        headers={"api-key": api_key, "Accept": "application/json"},
        timeout=15.0,
    ) as client:
        r = await client.get("/account")
    if not r.is_success:
        raise ValueError(f"Brevo connection failed: {r.status_code} {r.text}")
