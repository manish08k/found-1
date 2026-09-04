"""
Cisco Webex integration.

Webex REST API: https://developer.webex.com/docs/api/basics
Authentication: Bearer token (Personal Access Token or OAuth2 token)

Credential fields (api-key type):
  - access_token: Webex Personal Access Token or OAuth bearer token
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

WEBEX_BASE_URL = "https://webexapis.com/v1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    access_token = creds.get("access_token")
    if not access_token:
        raise ValueError("Webex credential missing 'access_token'")
    return httpx.AsyncClient(
        base_url=WEBEX_BASE_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
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
        raise ValueError(f"Webex API error {r.status_code}: {detail}")
    return r.json()


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

@register_node("webex.send_message")
async def webex_send_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /messages — send a message to a room or person."""
    payload: dict = {}
    for key in ("roomId", "toPersonId", "toPersonEmail", "text", "markdown", "files"):
        val = config.get(key) or input_data.get(key)
        if val is not None:
            payload[key] = val
    if not payload.get("roomId") and not payload.get("toPersonId") and not payload.get("toPersonEmail"):
        raise ValueError("webex.send_message requires 'roomId', 'toPersonId', or 'toPersonEmail'")
    if not payload.get("text") and not payload.get("markdown") and not payload.get("files"):
        raise ValueError("webex.send_message requires 'text', 'markdown', or 'files'")
    async with await _client(credential_id, db) as client:
        r = await client.post("/messages", json=payload)
    return {"message": _check(r)}


@register_node("webex.list_messages")
async def webex_list_messages(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /messages — list messages in a room."""
    room_id = config.get("roomId") or input_data.get("roomId")
    if not room_id:
        raise ValueError("webex.list_messages requires 'roomId'")
    params: dict = {"roomId": room_id}
    for key in ("max", "before", "beforeMessage", "mentionedPeople"):
        val = config.get(key) or input_data.get(key)
        if val is not None:
            params[key] = val
    async with await _client(credential_id, db) as client:
        r = await client.get("/messages", params=params)
    return _check(r)


@register_node("webex.get_message")
async def webex_get_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /messages/{id} — get a specific message."""
    message_id = config.get("messageId") or input_data.get("messageId")
    if not message_id:
        raise ValueError("webex.get_message requires 'messageId'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/messages/{message_id}")
    return {"message": _check(r)}


@register_node("webex.delete_message")
async def webex_delete_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /messages/{id} — delete a message."""
    message_id = config.get("messageId") or input_data.get("messageId")
    if not message_id:
        raise ValueError("webex.delete_message requires 'messageId'")
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/messages/{message_id}")
    if r.status_code == 204:
        return {"deleted": True, "messageId": message_id}
    _check(r)
    return {"deleted": True, "messageId": message_id}


# ---------------------------------------------------------------------------
# Rooms
# ---------------------------------------------------------------------------

@register_node("webex.list_rooms")
async def webex_list_rooms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /rooms — list rooms the authenticated user belongs to."""
    params: dict = {}
    for key in ("max", "type", "teamId", "sortBy"):
        val = config.get(key) or input_data.get(key)
        if val is not None:
            params[key] = val
    async with await _client(credential_id, db) as client:
        r = await client.get("/rooms", params=params)
    return _check(r)


@register_node("webex.get_room")
async def webex_get_room(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /rooms/{id} — get room details."""
    room_id = config.get("roomId") or input_data.get("roomId")
    if not room_id:
        raise ValueError("webex.get_room requires 'roomId'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/rooms/{room_id}")
    return {"room": _check(r)}


@register_node("webex.create_room")
async def webex_create_room(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /rooms — create a new Webex room/space."""
    title = config.get("title") or input_data.get("title")
    if not title:
        raise ValueError("webex.create_room requires 'title'")
    payload: dict = {"title": title}
    team_id = config.get("teamId") or input_data.get("teamId")
    if team_id:
        payload["teamId"] = team_id
    async with await _client(credential_id, db) as client:
        r = await client.post("/rooms", json=payload)
    return {"room": _check(r)}


@register_node("webex.update_room")
async def webex_update_room(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /rooms/{id} — update room title."""
    room_id = config.get("roomId") or input_data.get("roomId")
    title = config.get("title") or input_data.get("title")
    if not room_id or not title:
        raise ValueError("webex.update_room requires 'roomId' and 'title'")
    async with await _client(credential_id, db) as client:
        r = await client.put(f"/rooms/{room_id}", json={"title": title})
    return {"room": _check(r)}


# ---------------------------------------------------------------------------
# People / Users
# ---------------------------------------------------------------------------

@register_node("webex.get_me")
async def webex_get_me(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /people/me — get the authenticated user's profile."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/people/me")
    return {"person": _check(r)}


@register_node("webex.get_person")
async def webex_get_person(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /people/{id} — get a person by ID."""
    person_id = config.get("personId") or input_data.get("personId")
    if not person_id:
        raise ValueError("webex.get_person requires 'personId'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/people/{person_id}")
    return {"person": _check(r)}


@register_node("webex.list_people")
async def webex_list_people(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /people — search people by email or display name."""
    params: dict = {}
    for key in ("email", "displayName", "max"):
        val = config.get(key) or input_data.get(key)
        if val is not None:
            params[key] = val
    if not params:
        raise ValueError("webex.list_people requires at least 'email' or 'displayName'")
    async with await _client(credential_id, db) as client:
        r = await client.get("/people", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Memberships
# ---------------------------------------------------------------------------

@register_node("webex.list_memberships")
async def webex_list_memberships(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /memberships — list room memberships."""
    room_id = config.get("roomId") or input_data.get("roomId")
    if not room_id:
        raise ValueError("webex.list_memberships requires 'roomId'")
    async with await _client(credential_id, db) as client:
        r = await client.get("/memberships", params={"roomId": room_id})
    return _check(r)


@register_node("webex.add_membership")
async def webex_add_membership(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /memberships — add a person to a room."""
    room_id = config.get("roomId") or input_data.get("roomId")
    if not room_id:
        raise ValueError("webex.add_membership requires 'roomId'")
    payload: dict = {"roomId": room_id}
    for key in ("personId", "personEmail", "isModerator"):
        val = config.get(key) or input_data.get(key)
        if val is not None:
            payload[key] = val
    if "personId" not in payload and "personEmail" not in payload:
        raise ValueError("webex.add_membership requires 'personId' or 'personEmail'")
    async with await _client(credential_id, db) as client:
        r = await client.post("/memberships", json=payload)
    return {"membership": _check(r)}


@register_node("webex.delete_membership")
async def webex_delete_membership(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /memberships/{id} — remove a person from a room."""
    membership_id = config.get("membershipId") or input_data.get("membershipId")
    if not membership_id:
        raise ValueError("webex.delete_membership requires 'membershipId'")
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/memberships/{membership_id}")
    if r.status_code == 204:
        return {"deleted": True, "membershipId": membership_id}
    _check(r)
    return {"deleted": True, "membershipId": membership_id}


# ---------------------------------------------------------------------------
# Meetings
# ---------------------------------------------------------------------------

@register_node("webex.list_meetings")
async def webex_list_meetings(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /meetings — list upcoming meetings."""
    params: dict = {}
    for key in ("meetingType", "state", "max", "from", "to"):
        val = config.get(key) or input_data.get(key)
        if val is not None:
            params[key] = val
    async with await _client(credential_id, db) as client:
        r = await client.get("/meetings", params=params)
    return _check(r)


@register_node("webex.create_meeting")
async def webex_create_meeting(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /meetings — schedule a Webex meeting."""
    title = config.get("title") or input_data.get("title")
    start = config.get("start") or input_data.get("start")
    end = config.get("end") or input_data.get("end")
    if not title or not start or not end:
        raise ValueError("webex.create_meeting requires 'title', 'start', and 'end'")
    payload: dict = {"title": title, "start": start, "end": end}
    for key in ("password", "agenda", "enabledAutoRecordMeeting", "timezone"):
        val = config.get(key) or input_data.get(key)
        if val is not None:
            payload[key] = val
    async with await _client(credential_id, db) as client:
        r = await client.post("/meetings", json=payload)
    return {"meeting": _check(r)}


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(creds: dict) -> None:
    """Verify Webex credentials by fetching the authenticated user profile."""
    access_token = creds.get("access_token")
    if not access_token:
        raise ValueError("Webex requires 'access_token'")
    async with httpx.AsyncClient(
        base_url=WEBEX_BASE_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15.0,
    ) as client:
        r = await client.get("/people/me")
    if not r.is_success:
        raise ValueError(f"Webex connection failed: {r.status_code} {r.text[:200]}")
