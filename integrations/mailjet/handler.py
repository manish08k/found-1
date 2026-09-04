"""
Mailjet email delivery integration.

Credential fields:
  - api_key: Mailjet API key
  - api_secret: Mailjet API secret

Auth: HTTP Basic with api_key:api_secret
Base URL: https://api.mailjet.com/v3.1
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.mailjet.com/v3.1"
BASE_URL_V3 = "https://api.mailjet.com/v3"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    api_secret = creds.get("api_secret")
    if not api_key:
        raise ValueError("Mailjet credential is missing 'api_key'")
    if not api_secret:
        raise ValueError("Mailjet credential is missing 'api_secret'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        auth=(api_key, api_secret),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=30.0,
    )


async def _client_v3(credential_id: str, db) -> httpx.AsyncClient:
    """v3 REST client for data endpoints (contacts, lists, stats)."""
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    api_secret = creds.get("api_secret")
    if not api_key or not api_secret:
        raise ValueError("Mailjet credential is missing 'api_key' or 'api_secret'")
    return httpx.AsyncClient(
        base_url=BASE_URL_V3,
        auth=(api_key, api_secret),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Mailjet API error {r.status_code}: {detail}")
    if not r.content:
        return {}
    return r.json()


# ---------------------------------------------------------------------------
# Email sending
# ---------------------------------------------------------------------------

@register_node("mailjet.send_email")
async def mailjet_send_email(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /send — send one or more emails via Mailjet Send API v3.1."""
    messages = config.get("Messages") if config.get("Messages") is not None else input_data.get("Messages")
    if not messages:
        # Build a single message from individual fields
        to = config.get("to") if config.get("to") is not None else input_data.get("to")
        from_ = config.get("from") if config.get("from") is not None else input_data.get("from")
        subject = config.get("subject") if config.get("subject") is not None else input_data.get("subject")
        if not to or not from_ or not subject:
            raise ValueError("mailjet.send_email requires 'Messages' array or 'to', 'from', 'subject'")
        msg: dict = {
            "To": [{"Email": to}] if isinstance(to, str) else to,
            "From": {"Email": from_} if isinstance(from_, str) else from_,
            "Subject": subject,
        }
        text_part = config.get("TextPart") if config.get("TextPart") is not None else input_data.get("TextPart")
        if text_part is not None:
            msg["TextPart"] = text_part
        html_part = config.get("HTMLPart") if config.get("HTMLPart") is not None else input_data.get("HTMLPart")
        if html_part is not None:
            msg["HTMLPart"] = html_part
        messages = [msg]
    async with await _client(credential_id, db) as client:
        r = await client.post("/send", json={"Messages": messages})
    return _check(r)


@register_node("mailjet.list_messages")
async def mailjet_list_messages(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /REST/message — list sent messages."""
    params: dict = {}
    limit = config.get("Limit") if config.get("Limit") is not None else input_data.get("Limit")
    if limit is not None:
        params["Limit"] = int(limit)
    offset = config.get("Offset") if config.get("Offset") is not None else input_data.get("Offset")
    if offset is not None:
        params["Offset"] = int(offset)
    campaign_id = config.get("Campaign") if config.get("Campaign") is not None else input_data.get("Campaign")
    if campaign_id is not None:
        params["Campaign"] = campaign_id
    contact_email = config.get("ContactAlt") if config.get("ContactAlt") is not None else input_data.get("ContactAlt")
    if contact_email is not None:
        params["ContactAlt"] = contact_email
    async with await _client_v3(credential_id, db) as client:
        r = await client.get("/REST/message", params=params)
    return _check(r)


@register_node("mailjet.get_message")
async def mailjet_get_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /REST/message/{id} — get details for a specific message."""
    message_id = config.get("message_id") if config.get("message_id") is not None else input_data.get("message_id")
    if not message_id:
        raise ValueError("mailjet.get_message requires 'message_id'")
    async with await _client_v3(credential_id, db) as client:
        r = await client.get(f"/REST/message/{message_id}")
    return _check(r)


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

@register_node("mailjet.create_contact")
async def mailjet_create_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /REST/contact — create a new contact."""
    email = config.get("Email") if config.get("Email") is not None else input_data.get("Email")
    if not email:
        raise ValueError("mailjet.create_contact requires 'Email'")
    body: dict = {"Email": email}
    name = config.get("Name") if config.get("Name") is not None else input_data.get("Name")
    if name is not None:
        body["Name"] = name
    is_excluded_from_campaigns = config.get("IsExcludedFromCampaigns") if config.get("IsExcludedFromCampaigns") is not None else input_data.get("IsExcludedFromCampaigns")
    if is_excluded_from_campaigns is not None:
        body["IsExcludedFromCampaigns"] = bool(is_excluded_from_campaigns)
    async with await _client_v3(credential_id, db) as client:
        r = await client.post("/REST/contact", json=body)
    return _check(r)


@register_node("mailjet.list_contacts")
async def mailjet_list_contacts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /REST/contact — list contacts."""
    params: dict = {}
    limit = config.get("Limit") if config.get("Limit") is not None else input_data.get("Limit")
    if limit is not None:
        params["Limit"] = int(limit)
    offset = config.get("Offset") if config.get("Offset") is not None else input_data.get("Offset")
    if offset is not None:
        params["Offset"] = int(offset)
    async with await _client_v3(credential_id, db) as client:
        r = await client.get("/REST/contact", params=params)
    return _check(r)


@register_node("mailjet.subscribe_contact")
async def mailjet_subscribe_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /REST/listrecipient — subscribe a contact to a contact list."""
    contact_id = config.get("ContactID") if config.get("ContactID") is not None else input_data.get("ContactID")
    list_id = config.get("ListID") if config.get("ListID") is not None else input_data.get("ListID")
    if not contact_id or not list_id:
        raise ValueError("mailjet.subscribe_contact requires 'ContactID' and 'ListID'")
    body: dict = {"ContactID": contact_id, "ListID": list_id}
    is_unsubscribed = config.get("IsUnsubscribed") if config.get("IsUnsubscribed") is not None else input_data.get("IsUnsubscribed")
    if is_unsubscribed is not None:
        body["IsUnsubscribed"] = bool(is_unsubscribed)
    async with await _client_v3(credential_id, db) as client:
        r = await client.post("/REST/listrecipient", json=body)
    return _check(r)


@register_node("mailjet.list_contact_lists")
async def mailjet_list_contact_lists(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /REST/contactslist — list all contact lists."""
    params: dict = {}
    limit = config.get("Limit") if config.get("Limit") is not None else input_data.get("Limit")
    if limit is not None:
        params["Limit"] = int(limit)
    offset = config.get("Offset") if config.get("Offset") is not None else input_data.get("Offset")
    if offset is not None:
        params["Offset"] = int(offset)
    async with await _client_v3(credential_id, db) as client:
        r = await client.get("/REST/contactslist", params=params)
    return _check(r)


@register_node("mailjet.get_statistics")
async def mailjet_get_statistics(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /REST/statcounters — get campaign statistics."""
    params: dict = {"CounterSource": "Message", "CounterTiming": "Message", "CounterResolution": "Lifetime"}
    source_id = config.get("SourceID") if config.get("SourceID") is not None else input_data.get("SourceID")
    if source_id is not None:
        params["SourceID"] = source_id
    from_ts = config.get("FromTS") if config.get("FromTS") is not None else input_data.get("FromTS")
    if from_ts is not None:
        params["FromTS"] = from_ts
    to_ts = config.get("ToTS") if config.get("ToTS") is not None else input_data.get("ToTS")
    if to_ts is not None:
        params["ToTS"] = to_ts
    async with await _client_v3(credential_id, db) as client:
        r = await client.get("/REST/statcounters", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(creds: dict) -> None:
    """Test Mailjet credentials by fetching account info."""
    api_key = creds.get("api_key")
    api_secret = creds.get("api_secret")
    if not api_key or not api_secret:
        raise ValueError("Missing 'api_key' or 'api_secret'")
    async with httpx.AsyncClient(
        base_url=BASE_URL_V3,
        auth=(api_key, api_secret),
        headers={"Accept": "application/json"},
        timeout=15.0,
    ) as client:
        r = await client.get("/REST/apikey")
    if not r.is_success:
        raise ValueError(f"Mailjet connection failed: {r.status_code} {r.text}")
