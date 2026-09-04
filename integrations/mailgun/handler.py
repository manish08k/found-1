"""
Mailgun email integration.

Credential fields:
  - api_key: Mailgun API key
  - domain: Sending domain (e.g. mg.example.com)
  - region: 'us' or 'eu' (default: 'us')

Auth: HTTP Basic with user 'api' and api_key
Base URL: https://api.mailgun.net/v3 (US) or https://api.eu.mailgun.net/v3 (EU)
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URLS = {
    "us": "https://api.mailgun.net/v3",
    "eu": "https://api.eu.mailgun.net/v3",
}


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    domain = creds.get("domain")
    region = creds.get("region") or "us"
    if not api_key:
        raise ValueError("Mailgun credential is missing 'api_key'")
    if not domain:
        raise ValueError("Mailgun credential is missing 'domain'")
    if region not in BASE_URLS:
        raise ValueError(f"Mailgun region must be 'us' or 'eu', got: {region!r}")
    base_url = BASE_URLS[region]
    return httpx.AsyncClient(
        base_url=base_url,
        auth=("api", api_key),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Mailgun API error {r.status_code}: {detail}")
    if not r.content:
        return {}
    return r.json()


# ---------------------------------------------------------------------------
# Email sending
# ---------------------------------------------------------------------------

@register_node("mailgun.send_email")
async def mailgun_send_email(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /{domain}/messages — send an email via Mailgun."""
    creds = await get_credential_data(credential_id, db)
    domain = creds.get("domain")
    to = config.get("to") if config.get("to") is not None else input_data.get("to")
    from_ = config.get("from") if config.get("from") is not None else input_data.get("from")
    subject = config.get("subject") if config.get("subject") is not None else input_data.get("subject")
    if not to or not from_ or not subject:
        raise ValueError("mailgun.send_email requires 'to', 'from', and 'subject'")
    data: dict = {"to": to, "from": from_, "subject": subject}
    text = config.get("text") if config.get("text") is not None else input_data.get("text")
    if text is not None:
        data["text"] = text
    html = config.get("html") if config.get("html") is not None else input_data.get("html")
    if html is not None:
        data["html"] = html
    cc = config.get("cc") if config.get("cc") is not None else input_data.get("cc")
    if cc is not None:
        data["cc"] = cc
    bcc = config.get("bcc") if config.get("bcc") is not None else input_data.get("bcc")
    if bcc is not None:
        data["bcc"] = bcc
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/{domain}/messages", data=data)
    return _check(r)


@register_node("mailgun.list_messages")
async def mailgun_list_messages(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /{domain}/events — list stored messages/events."""
    creds = await get_credential_data(credential_id, db)
    domain = creds.get("domain")
    params: dict = {"event": "stored"}
    limit = config.get("limit") if config.get("limit") is not None else input_data.get("limit")
    if limit is not None:
        params["limit"] = int(limit)
    begin = config.get("begin") if config.get("begin") is not None else input_data.get("begin")
    if begin is not None:
        params["begin"] = begin
    end = config.get("end") if config.get("end") is not None else input_data.get("end")
    if end is not None:
        params["end"] = end
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/{domain}/events", params=params)
    return _check(r)


@register_node("mailgun.get_message")
async def mailgun_get_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /domains/{domain}/messages/{storage_key} — retrieve a stored message."""
    creds = await get_credential_data(credential_id, db)
    domain = creds.get("domain")
    storage_key = config.get("storage_key") if config.get("storage_key") is not None else input_data.get("storage_key")
    if not storage_key:
        raise ValueError("mailgun.get_message requires 'storage_key'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/domains/{domain}/messages/{storage_key}")
    return _check(r)


# ---------------------------------------------------------------------------
# Mailing lists
# ---------------------------------------------------------------------------

@register_node("mailgun.create_mailing_list")
async def mailgun_create_mailing_list(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /lists — create a new mailing list."""
    address = config.get("address") if config.get("address") is not None else input_data.get("address")
    if not address:
        raise ValueError("mailgun.create_mailing_list requires 'address'")
    data: dict = {"address": address}
    name = config.get("name") if config.get("name") is not None else input_data.get("name")
    if name is not None:
        data["name"] = name
    description = config.get("description") if config.get("description") is not None else input_data.get("description")
    if description is not None:
        data["description"] = description
    access_level = config.get("access_level") if config.get("access_level") is not None else input_data.get("access_level")
    if access_level is not None:
        data["access_level"] = access_level
    async with await _client(credential_id, db) as client:
        r = await client.post("/lists", data=data)
    return _check(r)


@register_node("mailgun.add_list_member")
async def mailgun_add_list_member(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /lists/{address}/members — add a member to a mailing list."""
    list_address = config.get("list_address") if config.get("list_address") is not None else input_data.get("list_address")
    member_email = config.get("member_email") if config.get("member_email") is not None else input_data.get("member_email")
    if not list_address or not member_email:
        raise ValueError("mailgun.add_list_member requires 'list_address' and 'member_email'")
    data: dict = {"address": member_email}
    name = config.get("name") if config.get("name") is not None else input_data.get("name")
    if name is not None:
        data["name"] = name
    subscribed = config.get("subscribed") if config.get("subscribed") is not None else input_data.get("subscribed")
    if subscribed is not None:
        data["subscribed"] = "yes" if subscribed else "no"
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/lists/{list_address}/members", data=data)
    return _check(r)


@register_node("mailgun.list_members")
async def mailgun_list_members(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /lists/{address}/members — list members of a mailing list."""
    list_address = config.get("list_address") if config.get("list_address") is not None else input_data.get("list_address")
    if not list_address:
        raise ValueError("mailgun.list_members requires 'list_address'")
    params: dict = {}
    limit = config.get("limit") if config.get("limit") is not None else input_data.get("limit")
    if limit is not None:
        params["limit"] = int(limit)
    subscribed = config.get("subscribed") if config.get("subscribed") is not None else input_data.get("subscribed")
    if subscribed is not None:
        params["subscribed"] = "yes" if subscribed else "no"
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/lists/{list_address}/members", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Email validation
# ---------------------------------------------------------------------------

@register_node("mailgun.validate_email")
async def mailgun_validate_email(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /address/validate — validate an email address."""
    address = config.get("address") if config.get("address") is not None else input_data.get("address")
    if not address:
        raise ValueError("mailgun.validate_email requires 'address'")
    async with await _client(credential_id, db) as client:
        r = await client.get("/address/validate", params={"address": address})
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(creds: dict) -> None:
    """Test Mailgun credentials by listing domains."""
    api_key = creds.get("api_key")
    region = creds.get("region") or "us"
    if not api_key:
        raise ValueError("Missing 'api_key'")
    base_url = BASE_URLS.get(region, BASE_URLS["us"])
    async with httpx.AsyncClient(base_url=base_url, auth=("api", api_key), timeout=15.0) as client:
        r = await client.get("/domains")
    if not r.is_success:
        raise ValueError(f"Mailgun connection failed: {r.status_code} {r.text}")
