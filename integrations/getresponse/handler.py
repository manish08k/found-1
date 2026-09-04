"""
GetResponse email marketing integration.

Credential fields:
  - api_key: GetResponse API key (sent as X-Auth-Token: api-key {key} header)

Base URL: https://api.getresponse.com/v3
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.getresponse.com/v3"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("GetResponse credential is missing 'api_key'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "X-Auth-Token": f"api-key {api_key}",
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
        raise ValueError(f"GetResponse API error {r.status_code}: {detail}")
    if not r.content:
        return {}
    return r.json()


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

@register_node("getresponse.create_contact")
async def getresponse_create_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /contacts — create a new contact."""
    email = config.get("email") if config.get("email") is not None else input_data.get("email")
    campaign = config.get("campaign") if config.get("campaign") is not None else input_data.get("campaign")
    if not email or not campaign:
        raise ValueError("getresponse.create_contact requires 'email' and 'campaign' (object with campaignId)")
    body: dict = {"email": email, "campaign": campaign}
    name = config.get("name") if config.get("name") is not None else input_data.get("name")
    if name is not None:
        body["name"] = name
    day_of_cycle = config.get("dayOfCycle") if config.get("dayOfCycle") is not None else input_data.get("dayOfCycle")
    if day_of_cycle is not None:
        body["dayOfCycle"] = int(day_of_cycle)
    custom_field_values = config.get("customFieldValues") if config.get("customFieldValues") is not None else input_data.get("customFieldValues")
    if custom_field_values is not None:
        body["customFieldValues"] = custom_field_values
    async with await _client(credential_id, db) as client:
        r = await client.post("/contacts", json=body)
    return _check(r)


@register_node("getresponse.get_contact")
async def getresponse_get_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /contacts/{id} — get a contact by ID."""
    contact_id = config.get("contact_id") if config.get("contact_id") is not None else input_data.get("contact_id")
    if not contact_id:
        raise ValueError("getresponse.get_contact requires 'contact_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/contacts/{contact_id}")
    return _check(r)


@register_node("getresponse.update_contact")
async def getresponse_update_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PATCH /contacts/{id} — update a contact."""
    contact_id = config.get("contact_id") if config.get("contact_id") is not None else input_data.get("contact_id")
    if not contact_id:
        raise ValueError("getresponse.update_contact requires 'contact_id'")
    body: dict = {}
    name = config.get("name") if config.get("name") is not None else input_data.get("name")
    if name is not None:
        body["name"] = name
    day_of_cycle = config.get("dayOfCycle") if config.get("dayOfCycle") is not None else input_data.get("dayOfCycle")
    if day_of_cycle is not None:
        body["dayOfCycle"] = int(day_of_cycle)
    custom_field_values = config.get("customFieldValues") if config.get("customFieldValues") is not None else input_data.get("customFieldValues")
    if custom_field_values is not None:
        body["customFieldValues"] = custom_field_values
    campaign = config.get("campaign") if config.get("campaign") is not None else input_data.get("campaign")
    if campaign is not None:
        body["campaign"] = campaign
    async with await _client(credential_id, db) as client:
        r = await client.patch(f"/contacts/{contact_id}", json=body)
    return _check(r)


@register_node("getresponse.delete_contact")
async def getresponse_delete_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /contacts/{id} — delete a contact."""
    contact_id = config.get("contact_id") if config.get("contact_id") is not None else input_data.get("contact_id")
    if not contact_id:
        raise ValueError("getresponse.delete_contact requires 'contact_id'")
    params: dict = {}
    message_id = config.get("messageId") if config.get("messageId") is not None else input_data.get("messageId")
    if message_id is not None:
        params["messageId"] = message_id
    ip_address = config.get("ipAddress") if config.get("ipAddress") is not None else input_data.get("ipAddress")
    if ip_address is not None:
        params["ipAddress"] = ip_address
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/contacts/{contact_id}", params=params)
    return _check(r)


@register_node("getresponse.list_contacts")
async def getresponse_list_contacts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /contacts — list contacts with optional filters."""
    params: dict = {}
    page = config.get("page") if config.get("page") is not None else input_data.get("page")
    if page is not None:
        params["page"] = int(page)
    per_page = config.get("perPage") if config.get("perPage") is not None else input_data.get("perPage")
    if per_page is not None:
        params["perPage"] = int(per_page)
    campaign_id = config.get("query[campaignId]") if config.get("query[campaignId]") is not None else input_data.get("query[campaignId]")
    if campaign_id is not None:
        params["query[campaignId]"] = campaign_id
    email = config.get("query[email]") if config.get("query[email]") is not None else input_data.get("query[email]")
    if email is not None:
        params["query[email]"] = email
    async with await _client(credential_id, db) as client:
        r = await client.get("/contacts", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Campaigns (lists)
# ---------------------------------------------------------------------------

@register_node("getresponse.list_campaigns")
async def getresponse_list_campaigns(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /campaigns — list all campaigns (lists)."""
    params: dict = {}
    page = config.get("page") if config.get("page") is not None else input_data.get("page")
    if page is not None:
        params["page"] = int(page)
    per_page = config.get("perPage") if config.get("perPage") is not None else input_data.get("perPage")
    if per_page is not None:
        params["perPage"] = int(per_page)
    name = config.get("query[name]") if config.get("query[name]") is not None else input_data.get("query[name]")
    if name is not None:
        params["query[name]"] = name
    async with await _client(credential_id, db) as client:
        r = await client.get("/campaigns", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Newsletters
# ---------------------------------------------------------------------------

@register_node("getresponse.create_newsletter")
async def getresponse_create_newsletter(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /newsletters — create a newsletter."""
    name = config.get("name") if config.get("name") is not None else input_data.get("name")
    subject = config.get("subject") if config.get("subject") is not None else input_data.get("subject")
    campaign = config.get("campaign") if config.get("campaign") is not None else input_data.get("campaign")
    from_field = config.get("fromField") if config.get("fromField") is not None else input_data.get("fromField")
    content = config.get("content") if config.get("content") is not None else input_data.get("content")
    if not name or not subject or not campaign or not from_field or not content:
        raise ValueError(
            "getresponse.create_newsletter requires 'name', 'subject', 'campaign', 'fromField', and 'content'"
        )
    body: dict = {
        "name": name,
        "subject": subject,
        "campaign": campaign,
        "fromField": from_field,
        "content": content,
    }
    send_settings = config.get("sendSettings") if config.get("sendSettings") is not None else input_data.get("sendSettings")
    if send_settings is not None:
        body["sendSettings"] = send_settings
    reply_to = config.get("replyTo") if config.get("replyTo") is not None else input_data.get("replyTo")
    if reply_to is not None:
        body["replyTo"] = reply_to
    async with await _client(credential_id, db) as client:
        r = await client.post("/newsletters", json=body)
    return _check(r)


@register_node("getresponse.list_newsletters")
async def getresponse_list_newsletters(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /newsletters — list newsletters."""
    params: dict = {}
    page = config.get("page") if config.get("page") is not None else input_data.get("page")
    if page is not None:
        params["page"] = int(page)
    per_page = config.get("perPage") if config.get("perPage") is not None else input_data.get("perPage")
    if per_page is not None:
        params["perPage"] = int(per_page)
    status = config.get("query[status]") if config.get("query[status]") is not None else input_data.get("query[status]")
    if status is not None:
        params["query[status]"] = status
    async with await _client(credential_id, db) as client:
        r = await client.get("/newsletters", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(creds: dict) -> None:
    """Test GetResponse credentials by fetching account info."""
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Missing 'api_key'")
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "X-Auth-Token": f"api-key {api_key}",
            "Accept": "application/json",
        },
        timeout=15.0,
    ) as client:
        r = await client.get("/accounts")
    if not r.is_success:
        raise ValueError(f"GetResponse connection failed: {r.status_code} {r.text}")
