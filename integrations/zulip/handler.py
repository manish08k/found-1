"""
Zulip integration.

Credential fields:
  - site: e.g. https://yourorg.zulipchat.com
  - email: bot or user email
  - api_key: Zulip API key

Auth: HTTP Basic with email:api_key
Base URL: {site}/api/v1
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    site = creds.get("site", "").rstrip("/")
    email = creds.get("email")
    api_key = creds.get("api_key")
    if not site:
        raise ValueError("Zulip credential is missing 'site'")
    if not email:
        raise ValueError("Zulip credential is missing 'email'")
    if not api_key:
        raise ValueError("Zulip credential is missing 'api_key'")
    base_url = f"{site}/api/v1"
    return httpx.AsyncClient(
        base_url=base_url,
        auth=(email, api_key),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Zulip API error {r.status_code}: {detail}")
    return r.json()


async def test_connection(credential_id: str, db) -> dict:
    """Verify credentials by fetching server settings."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/server_settings")
    return _check(r)


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

@register_node("zulip.send_message")
async def zulip_send_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /messages — send a message to a stream or direct."""
    msg_type = config.get("type") or input_data.get("type", "stream")
    to = config.get("to") or input_data.get("to")
    content = config.get("content") or input_data.get("content")
    if not to or not content:
        raise ValueError("zulip.send_message requires 'to' and 'content'")
    data: dict = {"type": msg_type, "to": to, "content": content}
    topic = config.get("topic") or input_data.get("topic")
    if topic:
        data["topic"] = topic
    async with await _client(credential_id, db) as client:
        r = await client.post("/messages", data=data)
    return _check(r)


@register_node("zulip.list_messages")
async def zulip_list_messages(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /messages — fetch messages from a narrow."""
    anchor = config.get("anchor") or input_data.get("anchor", "newest")
    num_before = config.get("num_before") or input_data.get("num_before", 10)
    num_after = config.get("num_after") or input_data.get("num_after", 0)
    params: dict = {
        "anchor": anchor,
        "num_before": int(num_before),
        "num_after": int(num_after),
    }
    narrow = config.get("narrow") or input_data.get("narrow")
    if narrow:
        import json
        params["narrow"] = json.dumps(narrow) if isinstance(narrow, list) else narrow
    async with await _client(credential_id, db) as client:
        r = await client.get("/messages", params=params)
    return _check(r)


@register_node("zulip.update_message")
async def zulip_update_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PATCH /messages/{message_id} — update a message."""
    message_id = config.get("message_id") or input_data.get("message_id")
    if not message_id:
        raise ValueError("zulip.update_message requires 'message_id'")
    data: dict = {}
    content = config.get("content") or input_data.get("content")
    if content:
        data["content"] = content
    topic = config.get("topic") or input_data.get("topic")
    if topic:
        data["topic"] = topic
    async with await _client(credential_id, db) as client:
        r = await client.patch(f"/messages/{message_id}", data=data)
    return _check(r)


@register_node("zulip.delete_message")
async def zulip_delete_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /messages/{message_id} — delete a message."""
    message_id = config.get("message_id") or input_data.get("message_id")
    if not message_id:
        raise ValueError("zulip.delete_message requires 'message_id'")
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/messages/{message_id}")
    return _check(r)


# ---------------------------------------------------------------------------
# Streams
# ---------------------------------------------------------------------------

@register_node("zulip.list_streams")
async def zulip_list_streams(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /streams — list all streams."""
    params = {}
    include_public = config.get("include_public")
    if include_public is None:
        include_public = input_data.get("include_public")
    if include_public is not None:
        params["include_public"] = str(include_public).lower()
    async with await _client(credential_id, db) as client:
        r = await client.get("/streams", params=params)
    return _check(r)


@register_node("zulip.get_stream")
async def zulip_get_stream(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /streams/{stream_id} — get a stream by ID."""
    stream_id = config.get("stream_id") or input_data.get("stream_id")
    if not stream_id:
        raise ValueError("zulip.get_stream requires 'stream_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/streams/{stream_id}")
    return _check(r)


@register_node("zulip.create_stream")
async def zulip_create_stream(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /users/me/subscriptions — create/subscribe to streams."""
    subscriptions = config.get("subscriptions") or input_data.get("subscriptions")
    if not subscriptions:
        raise ValueError("zulip.create_stream requires 'subscriptions' (list of {name} dicts)")
    import json
    data: dict = {
        "subscriptions": json.dumps(subscriptions) if isinstance(subscriptions, list) else subscriptions
    }
    invite_only = config.get("invite_only")
    if invite_only is None:
        invite_only = input_data.get("invite_only")
    if invite_only is not None:
        data["invite_only"] = str(invite_only).lower()
    async with await _client(credential_id, db) as client:
        r = await client.post("/users/me/subscriptions", data=data)
    return _check(r)


@register_node("zulip.list_topics")
async def zulip_list_topics(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /users/me/{stream_id}/topics — list topics in a stream."""
    stream_id = config.get("stream_id") or input_data.get("stream_id")
    if not stream_id:
        raise ValueError("zulip.list_topics requires 'stream_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/users/me/{stream_id}/topics")
    return _check(r)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@register_node("zulip.list_users")
async def zulip_list_users(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /users — list all users."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/users")
    return _check(r)


@register_node("zulip.get_user")
async def zulip_get_user(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /users/{user_id_or_email} — get a user by ID or email."""
    user_id = config.get("user_id") or input_data.get("user_id")
    email = config.get("email") or input_data.get("email")
    identifier = user_id or email
    if not identifier:
        raise ValueError("zulip.get_user requires 'user_id' or 'email'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/users/{identifier}")
    return _check(r)


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------

@register_node("zulip.upload_file")
async def zulip_upload_file(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /user_uploads — upload a file."""
    filename = config.get("filename") or input_data.get("filename")
    file_content = config.get("file_content") or input_data.get("file_content")
    if not filename or file_content is None:
        raise ValueError("zulip.upload_file requires 'filename' and 'file_content'")
    creds = await get_credential_data(credential_id, db)
    site = creds.get("site", "").rstrip("/")
    email = creds.get("email")
    api_key = creds.get("api_key")
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"{site}/api/v1/user_uploads",
            auth=(email, api_key),
            files={"filename": (filename, file_content)},
        )
    return _check(r)


# ---------------------------------------------------------------------------
# User Groups
# ---------------------------------------------------------------------------

@register_node("zulip.list_user_groups")
async def zulip_list_user_groups(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /user_groups — list user groups."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/user_groups")
    return _check(r)


# ---------------------------------------------------------------------------
# Event Queue
# ---------------------------------------------------------------------------

@register_node("zulip.register_event_queue")
async def zulip_register_event_queue(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /register — register an event queue."""
    data: dict = {}
    event_types = config.get("event_types") or input_data.get("event_types")
    if event_types:
        import json
        data["event_types"] = json.dumps(event_types) if isinstance(event_types, list) else event_types
    narrow = config.get("narrow") or input_data.get("narrow")
    if narrow:
        import json
        data["narrow"] = json.dumps(narrow) if isinstance(narrow, list) else narrow
    async with await _client(credential_id, db) as client:
        r = await client.post("/register", data=data)
    return _check(r)
