"""
Mattermost integration.

Credential fields:
  - url: e.g. https://mattermost.example.com
  - token: Personal Access Token or Bot Token

Auth: Authorization: Bearer {token}
Base URL: {url}/api/v4
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    url = creds.get("url", "").rstrip("/")
    token = creds.get("token")
    if not url:
        raise ValueError("Mattermost credential is missing 'url'")
    if not token:
        raise ValueError("Mattermost credential is missing 'token'")
    base_url = f"{url}/api/v4"
    return httpx.AsyncClient(
        base_url=base_url,
        headers={
            "Authorization": f"Bearer {token}",
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
        raise ValueError(f"Mattermost API error {r.status_code}: {detail}")
    try:
        return r.json()
    except Exception:
        return {"status": r.status_code, "text": r.text}


async def test_connection(credential_id: str, db) -> dict:
    """Verify credentials by fetching the current user."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/users/me")
    return _check(r)


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

@register_node("mattermost.list_teams")
async def mattermost_list_teams(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /teams — list all teams."""
    params = {}
    page = config.get("page") or input_data.get("page")
    if page is not None:
        params["page"] = int(page)
    per_page = config.get("per_page") or input_data.get("per_page")
    if per_page:
        params["per_page"] = int(per_page)
    async with await _client(credential_id, db) as client:
        r = await client.get("/teams", params=params)
    return {"teams": _check(r)}


@register_node("mattermost.get_team")
async def mattermost_get_team(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /teams/{team_id} — get a team by ID."""
    team_id = config.get("team_id") or input_data.get("team_id")
    if not team_id:
        raise ValueError("mattermost.get_team requires 'team_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/teams/{team_id}")
    return _check(r)


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------

@register_node("mattermost.list_channels")
async def mattermost_list_channels(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /teams/{team_id}/channels — list channels for a team."""
    team_id = config.get("team_id") or input_data.get("team_id")
    if not team_id:
        raise ValueError("mattermost.list_channels requires 'team_id'")
    params = {}
    page = config.get("page") or input_data.get("page")
    if page is not None:
        params["page"] = int(page)
    per_page = config.get("per_page") or input_data.get("per_page")
    if per_page:
        params["per_page"] = int(per_page)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/teams/{team_id}/channels", params=params)
    return {"channels": _check(r)}


@register_node("mattermost.get_channel")
async def mattermost_get_channel(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /channels/{channel_id} — get a channel by ID."""
    channel_id = config.get("channel_id") or input_data.get("channel_id")
    if not channel_id:
        raise ValueError("mattermost.get_channel requires 'channel_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/channels/{channel_id}")
    return _check(r)


@register_node("mattermost.create_channel")
async def mattermost_create_channel(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /channels — create a new channel."""
    team_id = config.get("team_id") or input_data.get("team_id")
    name = config.get("name") or input_data.get("name")
    display_name = config.get("display_name") or input_data.get("display_name")
    channel_type = config.get("type") or input_data.get("type", "O")
    if not team_id or not name or not display_name:
        raise ValueError("mattermost.create_channel requires 'team_id', 'name', and 'display_name'")
    body: dict = {
        "team_id": team_id,
        "name": name,
        "display_name": display_name,
        "type": channel_type,
    }
    purpose = config.get("purpose") or input_data.get("purpose")
    if purpose:
        body["purpose"] = purpose
    async with await _client(credential_id, db) as client:
        r = await client.post("/channels", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Posts / Messages
# ---------------------------------------------------------------------------

@register_node("mattermost.post_message")
async def mattermost_post_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /posts — post a message to a channel."""
    channel_id = config.get("channel_id") or input_data.get("channel_id")
    message = config.get("message") or input_data.get("message")
    if not channel_id or not message:
        raise ValueError("mattermost.post_message requires 'channel_id' and 'message'")
    body: dict = {"channel_id": channel_id, "message": message}
    root_id = config.get("root_id") or input_data.get("root_id")
    if root_id:
        body["root_id"] = root_id
    async with await _client(credential_id, db) as client:
        r = await client.post("/posts", json=body)
    return _check(r)


@register_node("mattermost.get_post")
async def mattermost_get_post(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /posts/{post_id} — get a post by ID."""
    post_id = config.get("post_id") or input_data.get("post_id")
    if not post_id:
        raise ValueError("mattermost.get_post requires 'post_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/posts/{post_id}")
    return _check(r)


@register_node("mattermost.list_posts")
async def mattermost_list_posts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /channels/{channel_id}/posts — list posts in a channel."""
    channel_id = config.get("channel_id") or input_data.get("channel_id")
    if not channel_id:
        raise ValueError("mattermost.list_posts requires 'channel_id'")
    params = {}
    page = config.get("page") or input_data.get("page")
    if page is not None:
        params["page"] = int(page)
    per_page = config.get("per_page") or input_data.get("per_page")
    if per_page:
        params["per_page"] = int(per_page)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/channels/{channel_id}/posts", params=params)
    return _check(r)


@register_node("mattermost.update_post")
async def mattermost_update_post(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /posts/{post_id} — update a post."""
    post_id = config.get("post_id") or input_data.get("post_id")
    message = config.get("message") or input_data.get("message")
    if not post_id or not message:
        raise ValueError("mattermost.update_post requires 'post_id' and 'message'")
    async with await _client(credential_id, db) as client:
        r = await client.put(f"/posts/{post_id}", json={"id": post_id, "message": message})
    return _check(r)


@register_node("mattermost.delete_post")
async def mattermost_delete_post(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /posts/{post_id} — delete a post."""
    post_id = config.get("post_id") or input_data.get("post_id")
    if not post_id:
        raise ValueError("mattermost.delete_post requires 'post_id'")
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/posts/{post_id}")
    return _check(r)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@register_node("mattermost.list_users")
async def mattermost_list_users(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /users — list users."""
    params = {}
    page = config.get("page") or input_data.get("page")
    if page is not None:
        params["page"] = int(page)
    per_page = config.get("per_page") or input_data.get("per_page")
    if per_page:
        params["per_page"] = int(per_page)
    in_team = config.get("in_team") or input_data.get("in_team")
    if in_team:
        params["in_team"] = in_team
    in_channel = config.get("in_channel") or input_data.get("in_channel")
    if in_channel:
        params["in_channel"] = in_channel
    async with await _client(credential_id, db) as client:
        r = await client.get("/users", params=params)
    return {"users": _check(r)}


@register_node("mattermost.get_user")
async def mattermost_get_user(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /users/{user_id} — get a user by ID."""
    user_id = config.get("user_id") or input_data.get("user_id", "me")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/users/{user_id}")
    return _check(r)


# ---------------------------------------------------------------------------
# Channel Members
# ---------------------------------------------------------------------------

@register_node("mattermost.add_channel_member")
async def mattermost_add_channel_member(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /channels/{channel_id}/members — add a user to a channel."""
    channel_id = config.get("channel_id") or input_data.get("channel_id")
    user_id = config.get("user_id") or input_data.get("user_id")
    if not channel_id or not user_id:
        raise ValueError("mattermost.add_channel_member requires 'channel_id' and 'user_id'")
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/channels/{channel_id}/members", json={"user_id": user_id})
    return _check(r)


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------

@register_node("mattermost.upload_file")
async def mattermost_upload_file(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /files — upload a file to a channel."""
    channel_id = config.get("channel_id") or input_data.get("channel_id")
    filename = config.get("filename") or input_data.get("filename")
    file_content = config.get("file_content") or input_data.get("file_content")
    if not channel_id or not filename or file_content is None:
        raise ValueError("mattermost.upload_file requires 'channel_id', 'filename', and 'file_content'")
    creds = await get_credential_data(credential_id, db)
    url = creds.get("url", "").rstrip("/")
    token = creds.get("token")
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"{url}/api/v4/files",
            headers={"Authorization": f"Bearer {token}"},
            params={"channel_id": channel_id},
            files={"files": (filename, file_content)},
        )
    return _check(r)


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------

@register_node("mattermost.create_webhook")
async def mattermost_create_webhook(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /hooks/incoming — create an incoming webhook."""
    channel_id = config.get("channel_id") or input_data.get("channel_id")
    if not channel_id:
        raise ValueError("mattermost.create_webhook requires 'channel_id'")
    body: dict = {"channel_id": channel_id}
    display_name = config.get("display_name") or input_data.get("display_name")
    if display_name:
        body["display_name"] = display_name
    description = config.get("description") or input_data.get("description")
    if description:
        body["description"] = description
    async with await _client(credential_id, db) as client:
        r = await client.post("/hooks/incoming", json=body)
    return _check(r)
