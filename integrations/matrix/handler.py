"""
Matrix chat protocol integration.

Provides messaging, room management, and user invitation via the
Matrix Client-Server API v3.

Credential fields:
  - homeserver_url : Base URL of the Matrix homeserver, e.g. https://matrix.example.com
  - access_token   : Bearer access token obtained via login or registration

Auth: Authorization: Bearer <access_token> header.
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    homeserver_url = creds.get("homeserver_url", "").rstrip("/")
    access_token = creds.get("access_token")
    if not homeserver_url:
        raise ValueError("Matrix credential missing 'homeserver_url'")
    if not access_token:
        raise ValueError("Matrix credential missing 'access_token'")
    return httpx.AsyncClient(
        base_url=f"{homeserver_url}/_matrix/client/v3",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Matrix API error {r.status_code}: {detail}")


@register_node("matrix.send_message")
async def matrix_send_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Send a message to a Matrix room."""
    room_id = config.get("room_id") or input_data.get("room_id")
    body = config.get("body") or input_data.get("body") or input_data.get("message", "")
    msg_type = config.get("msgtype") or input_data.get("msgtype", "m.text")

    if not room_id:
        raise ValueError("matrix.send_message requires 'room_id'")
    if not body:
        raise ValueError("matrix.send_message requires 'body'")

    # Use a timestamp-based transaction ID to ensure idempotency
    import time
    txn_id = str(int(time.time() * 1000))

    payload = {"msgtype": msg_type, "body": body}

    log.info("matrix.send_message", room_id=room_id)
    async with await _client(credential_id, db) as client:
        r = await client.put(f"/rooms/{room_id}/send/m.room.message/{txn_id}", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"event_id": data.get("event_id"), "room_id": room_id}


@register_node("matrix.create_room")
async def matrix_create_room(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new Matrix room."""
    name = config.get("name") or input_data.get("name", "")
    topic = config.get("topic") or input_data.get("topic", "")
    alias = config.get("alias") or input_data.get("alias", "")
    preset = config.get("preset") or input_data.get("preset", "private_chat")
    invite = config.get("invite") or input_data.get("invite", [])

    payload: dict = {"preset": preset}
    if name:
        payload["name"] = name
    if topic:
        payload["topic"] = topic
    if alias:
        payload["room_alias_name"] = alias
    if invite:
        payload["invite"] = invite if isinstance(invite, list) else [invite]

    log.info("matrix.create_room", name=name, preset=preset)
    async with await _client(credential_id, db) as client:
        r = await client.post("/createRoom", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"room_id": data.get("room_id"), "room_alias": data.get("room_alias")}


@register_node("matrix.invite_user")
async def matrix_invite_user(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Invite a user to a Matrix room."""
    room_id = config.get("room_id") or input_data.get("room_id")
    user_id = config.get("user_id") or input_data.get("user_id")

    if not room_id:
        raise ValueError("matrix.invite_user requires 'room_id'")
    if not user_id:
        raise ValueError("matrix.invite_user requires 'user_id'")

    log.info("matrix.invite_user", room_id=room_id, user_id=user_id)
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/rooms/{room_id}/invite", json={"user_id": user_id})
        _raise_for_status(r)

    return {"invited": True, "room_id": room_id, "user_id": user_id}


@register_node("matrix.list_rooms")
async def matrix_list_rooms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List joined Matrix rooms for the authenticated user."""
    log.info("matrix.list_rooms")
    async with await _client(credential_id, db) as client:
        r = await client.get("/joined_rooms")
        _raise_for_status(r)
        data = r.json()

    return {"rooms": data.get("joined_rooms", [])}
