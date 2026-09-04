"""
Rocket.Chat integration.

Credential fields:
  - url: e.g. https://chat.example.com
  - username: Rocket.Chat username
  - password: Rocket.Chat password
  (alternatively: auth_token + user_id for pre-authenticated sessions)

Auth: POST /api/v1/login to obtain X-Auth-Token and X-User-Id
Base URL: {url}/api/v1
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _login(url: str, username: str, password: str) -> tuple[str, str]:
    """Authenticate and return (auth_token, user_id)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{url}/api/v1/login",
            json={"user": username, "password": password},
        )
    if not r.is_success:
        raise ValueError(f"Rocket.Chat login failed {r.status_code}: {r.text}")
    data = r.json()
    if data.get("status") != "success":
        raise ValueError(f"Rocket.Chat login error: {data}")
    return data["data"]["authToken"], data["data"]["userId"]


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    url = creds.get("url", "").rstrip("/")
    if not url:
        raise ValueError("Rocket.Chat credential is missing 'url'")

    auth_token = creds.get("auth_token")
    user_id = creds.get("user_id")

    if not auth_token or not user_id:
        username = creds.get("username")
        password = creds.get("password")
        if not username or not password:
            raise ValueError("Rocket.Chat credential needs 'username'+'password' or 'auth_token'+'user_id'")
        auth_token, user_id = await _login(url, username, password)

    base_url = f"{url}/api/v1"
    return httpx.AsyncClient(
        base_url=base_url,
        headers={
            "X-Auth-Token": auth_token,
            "X-User-Id": user_id,
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Rocket.Chat API error {r.status_code}: {detail}")
    return r.json()


async def test_connection(credential_id: str, db) -> dict:
    """Verify credentials by fetching current user info."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/me")
    return _check(r)


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

@register_node("rocketchat.send_message")
async def rocketchat_send_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /chat.sendMessage — send a message to a room."""
    room_id = config.get("room_id") or input_data.get("room_id")
    text = config.get("text") or input_data.get("text")
    if not room_id or not text:
        raise ValueError("rocketchat.send_message requires 'room_id' and 'text'")
    body: dict = {"message": {"rid": room_id, "msg": text}}
    alias = config.get("alias") or input_data.get("alias")
    if alias:
        body["message"]["alias"] = alias
    async with await _client(credential_id, db) as client:
        r = await client.post("/chat.sendMessage", json=body)
    return _check(r)


@register_node("rocketchat.list_messages")
async def rocketchat_list_messages(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /channels.messages — list messages in a channel."""
    room_id = config.get("room_id") or input_data.get("room_id")
    if not room_id:
        raise ValueError("rocketchat.list_messages requires 'room_id'")
    params: dict = {"roomId": room_id}
    count = config.get("count") or input_data.get("count")
    if count:
        params["count"] = int(count)
    async with await _client(credential_id, db) as client:
        r = await client.get("/channels.messages", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------

@register_node("rocketchat.list_channels")
async def rocketchat_list_channels(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /channels.list — list public channels."""
    params = {}
    count = config.get("count") or input_data.get("count")
    if count:
        params["count"] = int(count)
    offset = config.get("offset") or input_data.get("offset")
    if offset:
        params["offset"] = int(offset)
    async with await _client(credential_id, db) as client:
        r = await client.get("/channels.list", params=params)
    return _check(r)


@register_node("rocketchat.get_channel_info")
async def rocketchat_get_channel_info(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /channels.info — get channel info by room ID or name."""
    room_id = config.get("room_id") or input_data.get("room_id")
    room_name = config.get("room_name") or input_data.get("room_name")
    if not room_id and not room_name:
        raise ValueError("rocketchat.get_channel_info requires 'room_id' or 'room_name'")
    params = {}
    if room_id:
        params["roomId"] = room_id
    elif room_name:
        params["roomName"] = room_name
    async with await _client(credential_id, db) as client:
        r = await client.get("/channels.info", params=params)
    return _check(r)


@register_node("rocketchat.create_channel")
async def rocketchat_create_channel(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /channels.create — create a public channel."""
    name = config.get("name") or input_data.get("name")
    if not name:
        raise ValueError("rocketchat.create_channel requires 'name'")
    body: dict = {"name": name}
    members = config.get("members") or input_data.get("members")
    if members:
        body["members"] = members
    async with await _client(credential_id, db) as client:
        r = await client.post("/channels.create", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@register_node("rocketchat.list_users")
async def rocketchat_list_users(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /users.list — list all users."""
    params = {}
    count = config.get("count") or input_data.get("count")
    if count:
        params["count"] = int(count)
    offset = config.get("offset") or input_data.get("offset")
    if offset:
        params["offset"] = int(offset)
    async with await _client(credential_id, db) as client:
        r = await client.get("/users.list", params=params)
    return _check(r)


@register_node("rocketchat.get_user")
async def rocketchat_get_user(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /users.info — get user info by ID or username."""
    user_id = config.get("user_id") or input_data.get("user_id")
    username = config.get("username") or input_data.get("username")
    if not user_id and not username:
        raise ValueError("rocketchat.get_user requires 'user_id' or 'username'")
    params = {}
    if user_id:
        params["userId"] = user_id
    elif username:
        params["username"] = username
    async with await _client(credential_id, db) as client:
        r = await client.get("/users.info", params=params)
    return _check(r)


@register_node("rocketchat.create_user")
async def rocketchat_create_user(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /users.create — create a new user."""
    email = config.get("email") or input_data.get("email")
    name = config.get("name") or input_data.get("name")
    username = config.get("username") or input_data.get("username")
    password = config.get("password") or input_data.get("password")
    if not email or not name or not username or not password:
        raise ValueError("rocketchat.create_user requires 'email', 'name', 'username', and 'password'")
    body: dict = {"email": email, "name": name, "username": username, "password": password}
    for field in ("roles", "verified", "active"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/users.create", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Groups (Private Channels)
# ---------------------------------------------------------------------------

@register_node("rocketchat.list_groups")
async def rocketchat_list_groups(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /groups.list — list private groups."""
    params = {}
    count = config.get("count") or input_data.get("count")
    if count:
        params["count"] = int(count)
    async with await _client(credential_id, db) as client:
        r = await client.get("/groups.list", params=params)
    return _check(r)


@register_node("rocketchat.create_group")
async def rocketchat_create_group(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /groups.create — create a private group."""
    name = config.get("name") or input_data.get("name")
    if not name:
        raise ValueError("rocketchat.create_group requires 'name'")
    body: dict = {"name": name}
    members = config.get("members") or input_data.get("members")
    if members:
        body["members"] = members
    async with await _client(credential_id, db) as client:
        r = await client.post("/groups.create", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Direct Messages
# ---------------------------------------------------------------------------

@register_node("rocketchat.send_direct_message")
async def rocketchat_send_direct_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /chat.postMessage to a direct message room."""
    username = config.get("username") or input_data.get("username")
    text = config.get("text") or input_data.get("text")
    if not username or not text:
        raise ValueError("rocketchat.send_direct_message requires 'username' and 'text'")
    body: dict = {"channel": f"@{username}", "text": text}
    async with await _client(credential_id, db) as client:
        r = await client.post("/chat.postMessage", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# File Upload
# ---------------------------------------------------------------------------

@register_node("rocketchat.upload_file")
async def rocketchat_upload_file(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /rooms.upload/{roomId} — upload a file to a room."""
    room_id = config.get("room_id") or input_data.get("room_id")
    filename = config.get("filename") or input_data.get("filename")
    file_content = config.get("file_content") or input_data.get("file_content")
    if not room_id or not filename or file_content is None:
        raise ValueError("rocketchat.upload_file requires 'room_id', 'filename', and 'file_content'")
    creds = await get_credential_data(credential_id, db)
    url = creds.get("url", "").rstrip("/")
    auth_token = creds.get("auth_token")
    user_id = creds.get("user_id")
    if not auth_token or not user_id:
        username = creds.get("username")
        password = creds.get("password")
        auth_token, user_id = await _login(url, username, password)
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"{url}/api/v1/rooms.upload/{room_id}",
            headers={"X-Auth-Token": auth_token, "X-User-Id": user_id},
            files={"file": (filename, file_content)},
        )
    return _check(r)
