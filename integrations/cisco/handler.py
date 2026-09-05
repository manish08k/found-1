"""
Cisco Webex Teams (Webex) messaging and collaboration integration.

Provides message sending, room management, and membership management
via the Webex REST API.

Credential fields:
  - access_token : Webex personal access token or bot token.
                   Obtained from developer.webex.com.

Auth: Bearer token via Authorization header.
Base URL: https://webexapis.com/v1/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://webexapis.com/v1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    access_token = creds.get("access_token")
    if not access_token:
        raise ValueError("Cisco Webex credential missing 'access_token'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Cisco Webex API error {r.status_code}: {detail}")


@register_node("cisco.send_message")
async def cisco_send_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Send a message to a Webex room or directly to a person.

    Params (one of room_id, to_person_id, or to_person_email required):
      - room_id: ID of the room to send the message to.
      - to_person_id: Webex person ID for a direct message.
      - to_person_email: Email address for a direct message.
      - text: Plain text message body.
      - markdown: Markdown-formatted message body.
      - html: HTML message body (limited subset).
      - files: Comma-separated list of public file URLs to attach.
      - parent_id: ID of a message to reply to (thread reply).
    """
    room_id = config.get("room_id") or input_data.get("room_id")
    to_person_id = config.get("to_person_id") or input_data.get("to_person_id")
    to_person_email = config.get("to_person_email") or input_data.get("to_person_email")

    if not room_id and not to_person_id and not to_person_email:
        raise ValueError(
            "cisco.send_message requires at least one of 'room_id', 'to_person_id', or 'to_person_email'"
        )

    text = config.get("text") or input_data.get("text")
    markdown = config.get("markdown") or input_data.get("markdown")
    html = config.get("html") or input_data.get("html")

    if not text and not markdown and not html:
        raise ValueError("cisco.send_message requires at least one of 'text', 'markdown', or 'html'")

    payload: dict = {}
    if room_id:
        payload["roomId"] = room_id
    elif to_person_id:
        payload["toPersonId"] = to_person_id
    else:
        payload["toPersonEmail"] = to_person_email

    if text:
        payload["text"] = text
    if markdown:
        payload["markdown"] = markdown
    if html:
        payload["html"] = html

    files_raw = config.get("files") or input_data.get("files")
    if files_raw:
        payload["files"] = [f.strip() for f in str(files_raw).split(",") if f.strip()]

    parent_id = config.get("parent_id") or input_data.get("parent_id")
    if parent_id:
        payload["parentId"] = parent_id

    async with await _client(credential_id, db) as client:
        r = await client.post("/messages", json=payload)
        _raise_for_status(r)
        data = r.json()

    log.info("cisco.send_message", message_id=data.get("id"), room_id=data.get("roomId"))
    return {"message": data, "id": data.get("id")}


@register_node("cisco.list_rooms")
async def cisco_list_rooms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    List Webex rooms (spaces) the authenticated user belongs to.

    Params:
      - type: Filter by room type — 'direct' or 'group'. Omit for both.
      - max: Max results to return (1-1000, default 100).
      - sort_by: 'id', 'lastactivity', 'created' (default 'lastactivity').
      - team_id: Restrict to rooms in a specific team.
    """
    room_type = config.get("type") or input_data.get("type")
    max_results = min(int(config.get("max") or input_data.get("max", 100)), 1000)
    sort_by = config.get("sort_by") or input_data.get("sort_by", "lastactivity")
    team_id = config.get("team_id") or input_data.get("team_id")

    params: dict = {"max": max_results, "sortBy": sort_by}
    if room_type:
        params["type"] = room_type
    if team_id:
        params["teamId"] = team_id

    async with await _client(credential_id, db) as client:
        r = await client.get("/rooms", params=params)
        _raise_for_status(r)
        data = r.json()

    rooms = data.get("items", [])
    log.info("cisco.list_rooms", count=len(rooms))
    return {"rooms": rooms, "count": len(rooms)}


@register_node("cisco.create_room")
async def cisco_create_room(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Create a new Webex room (space).

    Params:
      - title (required): The display name of the room.
      - team_id: ID of the team to associate the room with.
      - classification_id: Data classification label ID.
      - is_locked: bool — create a locked/moderated room.
      - is_public: bool — make the room publicly discoverable.
    """
    title = config.get("title") or input_data.get("title")
    if not title:
        raise ValueError("cisco.create_room requires 'title'")

    payload: dict = {"title": title}

    team_id = config.get("team_id") or input_data.get("team_id")
    if team_id:
        payload["teamId"] = team_id

    classification_id = config.get("classification_id") or input_data.get("classification_id")
    if classification_id:
        payload["classificationId"] = classification_id

    is_locked = config.get("is_locked")
    if is_locked is None:
        is_locked = input_data.get("is_locked")
    if is_locked is not None:
        payload["isLocked"] = bool(is_locked)

    is_public = config.get("is_public")
    if is_public is None:
        is_public = input_data.get("is_public")
    if is_public is not None:
        payload["isPublic"] = bool(is_public)

    async with await _client(credential_id, db) as client:
        r = await client.post("/rooms", json=payload)
        _raise_for_status(r)
        data = r.json()

    log.info("cisco.create_room", room_id=data.get("id"), title=title)
    return {"room": data, "id": data.get("id"), "title": data.get("title")}


@register_node("cisco.list_memberships")
async def cisco_list_memberships(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    List memberships for a room or for the authenticated person.

    Params:
      - room_id: Filter memberships to a specific room ID.
      - person_id: Filter memberships for a specific person.
      - person_email: Filter memberships for a specific person by email.
      - max: Max results (1-1000, default 100).
    """
    room_id = config.get("room_id") or input_data.get("room_id")
    person_id = config.get("person_id") or input_data.get("person_id")
    person_email = config.get("person_email") or input_data.get("person_email")
    max_results = min(int(config.get("max") or input_data.get("max", 100)), 1000)

    params: dict = {"max": max_results}
    if room_id:
        params["roomId"] = room_id
    if person_id:
        params["personId"] = person_id
    if person_email:
        params["personEmail"] = person_email

    async with await _client(credential_id, db) as client:
        r = await client.get("/memberships", params=params)
        _raise_for_status(r)
        data = r.json()

    memberships = data.get("items", [])
    log.info("cisco.list_memberships", count=len(memberships))
    return {"memberships": memberships, "count": len(memberships)}


@register_node("cisco.add_membership")
async def cisco_add_membership(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Add a person to a Webex room.

    Params:
      - room_id (required): ID of the room.
      - person_id: Webex person ID of the user to add.
      - person_email: Email of the user to add (alternative to person_id).
      - is_moderator: bool — grant moderator role (default False).
    """
    room_id = config.get("room_id") or input_data.get("room_id")
    if not room_id:
        raise ValueError("cisco.add_membership requires 'room_id'")

    person_id = config.get("person_id") or input_data.get("person_id")
    person_email = config.get("person_email") or input_data.get("person_email")

    if not person_id and not person_email:
        raise ValueError("cisco.add_membership requires 'person_id' or 'person_email'")

    payload: dict = {"roomId": room_id}
    if person_id:
        payload["personId"] = person_id
    else:
        payload["personEmail"] = person_email

    is_moderator = config.get("is_moderator")
    if is_moderator is None:
        is_moderator = input_data.get("is_moderator", False)
    payload["isModerator"] = bool(is_moderator)

    async with await _client(credential_id, db) as client:
        r = await client.post("/memberships", json=payload)
        _raise_for_status(r)
        data = r.json()

    log.info("cisco.add_membership", membership_id=data.get("id"), room_id=room_id)
    return {"membership": data, "id": data.get("id")}
