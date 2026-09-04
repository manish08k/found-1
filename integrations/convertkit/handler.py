"""
ConvertKit email marketing integration.

Credential fields:
  - api_key: ConvertKit public API key
  - api_secret: ConvertKit API secret (for certain endpoints)

Base URL: https://api.convertkit.com/v3
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.convertkit.com/v3"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("ConvertKit credential is missing 'api_key'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=30.0,
    )


async def _get_creds(credential_id: str, db) -> dict:
    return await get_credential_data(credential_id, db)


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"ConvertKit API error {r.status_code}: {detail}")
    if not r.content:
        return {}
    return r.json()


# ---------------------------------------------------------------------------
# Subscribers
# ---------------------------------------------------------------------------

@register_node("convertkit.list_subscribers")
async def convertkit_list_subscribers(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /subscribers — list all subscribers."""
    creds = await _get_creds(credential_id, db)
    api_secret = creds.get("api_secret") or creds.get("api_key")
    params: dict = {"api_secret": api_secret}
    page = config.get("page") if config.get("page") is not None else input_data.get("page")
    if page is not None:
        params["page"] = int(page)
    from_date = config.get("from") if config.get("from") is not None else input_data.get("from")
    if from_date is not None:
        params["from"] = from_date
    to_date = config.get("to") if config.get("to") is not None else input_data.get("to")
    if to_date is not None:
        params["to"] = to_date
    sort_field = config.get("sort_field") if config.get("sort_field") is not None else input_data.get("sort_field")
    if sort_field is not None:
        params["sort_field"] = sort_field
    async with await _client(credential_id, db) as client:
        r = await client.get("/subscribers", params=params)
    return _check(r)


@register_node("convertkit.get_subscriber")
async def convertkit_get_subscriber(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /subscribers/{id} — get a subscriber by ID."""
    creds = await _get_creds(credential_id, db)
    api_secret = creds.get("api_secret") or creds.get("api_key")
    subscriber_id = config.get("subscriber_id") if config.get("subscriber_id") is not None else input_data.get("subscriber_id")
    if not subscriber_id:
        raise ValueError("convertkit.get_subscriber requires 'subscriber_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/subscribers/{subscriber_id}", params={"api_secret": api_secret})
    return _check(r)


@register_node("convertkit.update_subscriber")
async def convertkit_update_subscriber(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /subscribers/{id} — update subscriber fields."""
    creds = await _get_creds(credential_id, db)
    api_secret = creds.get("api_secret") or creds.get("api_key")
    subscriber_id = config.get("subscriber_id") if config.get("subscriber_id") is not None else input_data.get("subscriber_id")
    if not subscriber_id:
        raise ValueError("convertkit.update_subscriber requires 'subscriber_id'")
    body: dict = {"api_secret": api_secret}
    first_name = config.get("first_name") if config.get("first_name") is not None else input_data.get("first_name")
    if first_name is not None:
        body["first_name"] = first_name
    email_address = config.get("email_address") if config.get("email_address") is not None else input_data.get("email_address")
    if email_address is not None:
        body["email_address"] = email_address
    fields = config.get("fields") if config.get("fields") is not None else input_data.get("fields")
    if fields is not None:
        body["fields"] = fields
    async with await _client(credential_id, db) as client:
        r = await client.put(f"/subscribers/{subscriber_id}", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Forms
# ---------------------------------------------------------------------------

@register_node("convertkit.list_forms")
async def convertkit_list_forms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /forms — list all forms."""
    creds = await _get_creds(credential_id, db)
    api_key = creds.get("api_key")
    async with await _client(credential_id, db) as client:
        r = await client.get("/forms", params={"api_key": api_key})
    return _check(r)


@register_node("convertkit.add_subscriber_to_form")
async def convertkit_add_subscriber_to_form(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /forms/{id}/subscribe — subscribe an email to a form."""
    creds = await _get_creds(credential_id, db)
    api_key = creds.get("api_key")
    form_id = config.get("form_id") if config.get("form_id") is not None else input_data.get("form_id")
    email = config.get("email") if config.get("email") is not None else input_data.get("email")
    if not form_id or not email:
        raise ValueError("convertkit.add_subscriber_to_form requires 'form_id' and 'email'")
    body: dict = {"api_key": api_key, "email": email}
    first_name = config.get("first_name") if config.get("first_name") is not None else input_data.get("first_name")
    if first_name is not None:
        body["first_name"] = first_name
    fields = config.get("fields") if config.get("fields") is not None else input_data.get("fields")
    if fields is not None:
        body["fields"] = fields
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/forms/{form_id}/subscribe", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Sequences
# ---------------------------------------------------------------------------

@register_node("convertkit.list_sequences")
async def convertkit_list_sequences(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /sequences — list all sequences (automations)."""
    creds = await _get_creds(credential_id, db)
    api_key = creds.get("api_key")
    async with await _client(credential_id, db) as client:
        r = await client.get("/sequences", params={"api_key": api_key})
    return _check(r)


@register_node("convertkit.add_subscriber_to_sequence")
async def convertkit_add_subscriber_to_sequence(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /sequences/{id}/subscribe — add a subscriber to a sequence."""
    creds = await _get_creds(credential_id, db)
    api_key = creds.get("api_key")
    sequence_id = config.get("sequence_id") if config.get("sequence_id") is not None else input_data.get("sequence_id")
    email = config.get("email") if config.get("email") is not None else input_data.get("email")
    if not sequence_id or not email:
        raise ValueError("convertkit.add_subscriber_to_sequence requires 'sequence_id' and 'email'")
    body: dict = {"api_key": api_key, "email": email}
    first_name = config.get("first_name") if config.get("first_name") is not None else input_data.get("first_name")
    if first_name is not None:
        body["first_name"] = first_name
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/sequences/{sequence_id}/subscribe", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

@register_node("convertkit.list_tags")
async def convertkit_list_tags(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /tags — list all tags."""
    creds = await _get_creds(credential_id, db)
    api_key = creds.get("api_key")
    async with await _client(credential_id, db) as client:
        r = await client.get("/tags", params={"api_key": api_key})
    return _check(r)


@register_node("convertkit.tag_subscriber")
async def convertkit_tag_subscriber(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /tags/{id}/subscribe — apply a tag to a subscriber by email."""
    creds = await _get_creds(credential_id, db)
    api_key = creds.get("api_key")
    tag_id = config.get("tag_id") if config.get("tag_id") is not None else input_data.get("tag_id")
    email = config.get("email") if config.get("email") is not None else input_data.get("email")
    if not tag_id or not email:
        raise ValueError("convertkit.tag_subscriber requires 'tag_id' and 'email'")
    body: dict = {"api_key": api_key, "email": email}
    first_name = config.get("first_name") if config.get("first_name") is not None else input_data.get("first_name")
    if first_name is not None:
        body["first_name"] = first_name
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/tags/{tag_id}/subscribe", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Broadcasts
# ---------------------------------------------------------------------------

@register_node("convertkit.list_broadcasts")
async def convertkit_list_broadcasts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /broadcasts — list all broadcasts."""
    creds = await _get_creds(credential_id, db)
    api_secret = creds.get("api_secret") or creds.get("api_key")
    async with await _client(credential_id, db) as client:
        r = await client.get("/broadcasts", params={"api_secret": api_secret})
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(creds: dict) -> None:
    """Test ConvertKit credentials by listing forms."""
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Missing 'api_key'")
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        headers={"Accept": "application/json"},
        timeout=15.0,
    ) as client:
        r = await client.get("/forms", params={"api_key": api_key})
    if not r.is_success:
        raise ValueError(f"ConvertKit connection failed: {r.status_code} {r.text}")
