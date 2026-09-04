"""
MailerLite email marketing integration.

Credential fields:
  - api_key: MailerLite API key (sent as Authorization: Bearer header)

Base URL: https://connect.mailerlite.com/api
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://connect.mailerlite.com/api"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("MailerLite credential is missing 'api_key'")
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
        raise ValueError(f"MailerLite API error {r.status_code}: {detail}")
    if not r.content:
        return {}
    return r.json()


# ---------------------------------------------------------------------------
# Subscribers
# ---------------------------------------------------------------------------

@register_node("mailerlite.create_subscriber")
async def mailerlite_create_subscriber(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /subscribers — create or update a subscriber."""
    email = config.get("email") if config.get("email") is not None else input_data.get("email")
    if not email:
        raise ValueError("mailerlite.create_subscriber requires 'email'")
    body: dict = {"email": email}
    fields = config.get("fields") if config.get("fields") is not None else input_data.get("fields")
    if fields is not None:
        body["fields"] = fields
    groups = config.get("groups") if config.get("groups") is not None else input_data.get("groups")
    if groups is not None:
        body["groups"] = groups
    status = config.get("status") if config.get("status") is not None else input_data.get("status")
    if status is not None:
        body["status"] = status
    async with await _client(credential_id, db) as client:
        r = await client.post("/subscribers", json=body)
    return _check(r)


@register_node("mailerlite.get_subscriber")
async def mailerlite_get_subscriber(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /subscribers/{id} — retrieve a subscriber by ID or email."""
    subscriber_id = config.get("subscriber_id") if config.get("subscriber_id") is not None else input_data.get("subscriber_id")
    if not subscriber_id:
        raise ValueError("mailerlite.get_subscriber requires 'subscriber_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/subscribers/{subscriber_id}")
    return _check(r)


@register_node("mailerlite.update_subscriber")
async def mailerlite_update_subscriber(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /subscribers/{id} — update a subscriber's fields and groups."""
    subscriber_id = config.get("subscriber_id") if config.get("subscriber_id") is not None else input_data.get("subscriber_id")
    if not subscriber_id:
        raise ValueError("mailerlite.update_subscriber requires 'subscriber_id'")
    body: dict = {}
    fields = config.get("fields") if config.get("fields") is not None else input_data.get("fields")
    if fields is not None:
        body["fields"] = fields
    groups = config.get("groups") if config.get("groups") is not None else input_data.get("groups")
    if groups is not None:
        body["groups"] = groups
    status = config.get("status") if config.get("status") is not None else input_data.get("status")
    if status is not None:
        body["status"] = status
    async with await _client(credential_id, db) as client:
        r = await client.put(f"/subscribers/{subscriber_id}", json=body)
    return _check(r)


@register_node("mailerlite.delete_subscriber")
async def mailerlite_delete_subscriber(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /subscribers/{id} — delete a subscriber."""
    subscriber_id = config.get("subscriber_id") if config.get("subscriber_id") is not None else input_data.get("subscriber_id")
    if not subscriber_id:
        raise ValueError("mailerlite.delete_subscriber requires 'subscriber_id'")
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/subscribers/{subscriber_id}")
    return _check(r)


@register_node("mailerlite.list_subscribers")
async def mailerlite_list_subscribers(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /subscribers — list subscribers."""
    params: dict = {}
    limit = config.get("limit") if config.get("limit") is not None else input_data.get("limit")
    if limit is not None:
        params["limit"] = int(limit)
    page = config.get("page") if config.get("page") is not None else input_data.get("page")
    if page is not None:
        params["page"] = int(page)
    filter_status = config.get("filter[status]") if config.get("filter[status]") is not None else input_data.get("filter[status]")
    if filter_status is not None:
        params["filter[status]"] = filter_status
    async with await _client(credential_id, db) as client:
        r = await client.get("/subscribers", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------

@register_node("mailerlite.create_group")
async def mailerlite_create_group(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /groups — create a new subscriber group."""
    name = config.get("name") if config.get("name") is not None else input_data.get("name")
    if not name:
        raise ValueError("mailerlite.create_group requires 'name'")
    async with await _client(credential_id, db) as client:
        r = await client.post("/groups", json={"name": name})
    return _check(r)


@register_node("mailerlite.list_groups")
async def mailerlite_list_groups(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /groups — list all subscriber groups."""
    params: dict = {}
    limit = config.get("limit") if config.get("limit") is not None else input_data.get("limit")
    if limit is not None:
        params["limit"] = int(limit)
    page = config.get("page") if config.get("page") is not None else input_data.get("page")
    if page is not None:
        params["page"] = int(page)
    async with await _client(credential_id, db) as client:
        r = await client.get("/groups", params=params)
    return _check(r)


@register_node("mailerlite.add_subscriber_to_group")
async def mailerlite_add_subscriber_to_group(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /groups/{group_id}/subscribers/{subscriber_id} — add subscriber to group."""
    group_id = config.get("group_id") if config.get("group_id") is not None else input_data.get("group_id")
    subscriber_id = config.get("subscriber_id") if config.get("subscriber_id") is not None else input_data.get("subscriber_id")
    if not group_id or not subscriber_id:
        raise ValueError("mailerlite.add_subscriber_to_group requires 'group_id' and 'subscriber_id'")
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/groups/{group_id}/subscribers/{subscriber_id}")
    return _check(r)


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------

@register_node("mailerlite.create_campaign")
async def mailerlite_create_campaign(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /campaigns — create an email campaign."""
    name = config.get("name") if config.get("name") is not None else input_data.get("name")
    type_ = config.get("type") if config.get("type") is not None else input_data.get("type")
    if not name or not type_:
        raise ValueError("mailerlite.create_campaign requires 'name' and 'type'")
    body: dict = {"name": name, "type": type_}
    emails = config.get("emails") if config.get("emails") is not None else input_data.get("emails")
    if emails is not None:
        body["emails"] = emails
    groups = config.get("groups") if config.get("groups") is not None else input_data.get("groups")
    if groups is not None:
        body["groups"] = groups
    async with await _client(credential_id, db) as client:
        r = await client.post("/campaigns", json=body)
    return _check(r)


@register_node("mailerlite.list_campaigns")
async def mailerlite_list_campaigns(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /campaigns — list campaigns."""
    params: dict = {}
    limit = config.get("limit") if config.get("limit") is not None else input_data.get("limit")
    if limit is not None:
        params["limit"] = int(limit)
    page = config.get("page") if config.get("page") is not None else input_data.get("page")
    if page is not None:
        params["page"] = int(page)
    status = config.get("filter[status]") if config.get("filter[status]") is not None else input_data.get("filter[status]")
    if status is not None:
        params["filter[status]"] = status
    async with await _client(credential_id, db) as client:
        r = await client.get("/campaigns", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(creds: dict) -> None:
    """Test MailerLite credentials by fetching current user info."""
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Missing 'api_key'")
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        timeout=15.0,
    ) as client:
        r = await client.get("/me")
    if not r.is_success:
        raise ValueError(f"MailerLite connection failed: {r.status_code} {r.text}")
