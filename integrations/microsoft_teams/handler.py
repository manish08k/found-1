"""
Microsoft Teams integration via Microsoft Graph API.

Credential fields: {"access_token": "...", "tenant_id": "..."}
Auth: Bearer token against https://graph.microsoft.com/v1.0
"""
import json
import structlog
import httpx

from core.execution_engine import register_node
from core.ssrf_guard import assert_safe_url
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    token = creds.get("access_token")
    if not token:
        raise ValueError("Microsoft Teams credential is missing 'access_token'")
    return httpx.AsyncClient(
        base_url=GRAPH_BASE,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    """Raise descriptive errors including 429 rate-limit."""
    if r.status_code == 429:
        retry_after = r.headers.get("Retry-After", "unknown")
        raise ValueError(f"Microsoft Teams rate limit hit (429). Retry-After: {retry_after}s")
    if r.is_error:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Microsoft Teams API error {r.status_code}: {detail}")


# ─── Send message to channel ─────────────────────────────────────────────────

@register_node("teams.send_message")
async def teams_send_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    team_id = config.get("team_id") or input_data.get("team_id")
    channel_id = config.get("channel_id") or input_data.get("channel_id")
    content = config.get("content") or input_data.get("content", "")
    content_type = config.get("content_type", "text")  # "text" or "html"

    if not team_id:
        raise ValueError("teams.send_message requires 'team_id'")
    if not channel_id:
        raise ValueError("teams.send_message requires 'channel_id'")

    payload = {
        "body": {
            "contentType": content_type,
            "content": content,
        }
    }

    async with await _client(credential_id, db) as client:
        r = await client.post(
            f"/teams/{team_id}/channels/{channel_id}/messages",
            content=json.dumps(payload),
        )
        _raise_for_status(r)
        return r.json()


# ─── Send channel message (find channel by name first if provided) ────────────

@register_node("teams.send_channel_message")
async def teams_send_channel_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    team_id = config.get("team_id") or input_data.get("team_id")
    channel_id = config.get("channel_id") or input_data.get("channel_id")
    channel_name = config.get("channel_name") or input_data.get("channel_name")
    content = config.get("content") or input_data.get("content", "")
    content_type = config.get("content_type", "text")

    if not team_id:
        raise ValueError("teams.send_channel_message requires 'team_id'")

    async with await _client(credential_id, db) as client:
        # Resolve channel by name if channel_id not provided
        if not channel_id and channel_name:
            r = await client.get(f"/teams/{team_id}/channels")
            _raise_for_status(r)
            channels = r.json().get("value", [])
            matched = [c for c in channels if c.get("displayName", "").lower() == channel_name.lower()]
            if not matched:
                raise ValueError(f"Channel named '{channel_name}' not found in team {team_id}")
            channel_id = matched[0]["id"]

        if not channel_id:
            raise ValueError("teams.send_channel_message requires 'channel_id' or 'channel_name'")

        payload = {
            "body": {
                "contentType": content_type,
                "content": content,
            }
        }
        r = await client.post(
            f"/teams/{team_id}/channels/{channel_id}/messages",
            content=json.dumps(payload),
        )
        _raise_for_status(r)
        return r.json()


# ─── Reply to message ─────────────────────────────────────────────────────────

@register_node("teams.reply_to_message")
async def teams_reply_to_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    team_id = config.get("team_id") or input_data.get("team_id")
    channel_id = config.get("channel_id") or input_data.get("channel_id")
    message_id = config.get("message_id") or input_data.get("message_id")
    content = config.get("content") or input_data.get("content", "")
    content_type = config.get("content_type", "text")

    if not team_id:
        raise ValueError("teams.reply_to_message requires 'team_id'")
    if not channel_id:
        raise ValueError("teams.reply_to_message requires 'channel_id'")
    if not message_id:
        raise ValueError("teams.reply_to_message requires 'message_id'")

    payload = {
        "body": {
            "contentType": content_type,
            "content": content,
        }
    }

    async with await _client(credential_id, db) as client:
        r = await client.post(
            f"/teams/{team_id}/channels/{channel_id}/messages/{message_id}/replies",
            content=json.dumps(payload),
        )
        _raise_for_status(r)
        return r.json()


# ─── List teams ───────────────────────────────────────────────────────────────

@register_node("teams.list_teams")
async def teams_list_teams(config: dict, input_data: dict, credential_id: str, db) -> dict:
    async with await _client(credential_id, db) as client:
        r = await client.get("/me/joinedTeams")
        _raise_for_status(r)
        data = r.json()
    return {"teams": data.get("value", []), "count": len(data.get("value", []))}


# ─── List channels ────────────────────────────────────────────────────────────

@register_node("teams.list_channels")
async def teams_list_channels(config: dict, input_data: dict, credential_id: str, db) -> dict:
    team_id = config.get("team_id") or input_data.get("team_id")
    if not team_id:
        raise ValueError("teams.list_channels requires 'team_id'")

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/teams/{team_id}/channels")
        _raise_for_status(r)
        data = r.json()
    return {"channels": data.get("value", []), "count": len(data.get("value", []))}


# ─── Create channel ───────────────────────────────────────────────────────────

@register_node("teams.create_channel")
async def teams_create_channel(config: dict, input_data: dict, credential_id: str, db) -> dict:
    team_id = config.get("team_id") or input_data.get("team_id")
    display_name = config.get("display_name") or input_data.get("display_name")
    description = config.get("description") or input_data.get("description", "")
    membership_type = config.get("membership_type", "standard")  # "standard" or "private"

    if not team_id:
        raise ValueError("teams.create_channel requires 'team_id'")
    if not display_name:
        raise ValueError("teams.create_channel requires 'display_name'")
    if membership_type not in ("standard", "private"):
        raise ValueError("teams.create_channel: 'membership_type' must be 'standard' or 'private'")

    payload = {
        "displayName": display_name,
        "description": description,
        "membershipType": membership_type,
    }

    async with await _client(credential_id, db) as client:
        r = await client.post(f"/teams/{team_id}/channels", content=json.dumps(payload))
        _raise_for_status(r)
        return r.json()


# ─── Get messages ─────────────────────────────────────────────────────────────

@register_node("teams.get_messages")
async def teams_get_messages(config: dict, input_data: dict, credential_id: str, db) -> dict:
    team_id = config.get("team_id") or input_data.get("team_id")
    channel_id = config.get("channel_id") or input_data.get("channel_id")
    top = min(int(config.get("top", 20)), 50)

    if not team_id:
        raise ValueError("teams.get_messages requires 'team_id'")
    if not channel_id:
        raise ValueError("teams.get_messages requires 'channel_id'")

    async with await _client(credential_id, db) as client:
        r = await client.get(
            f"/teams/{team_id}/channels/{channel_id}/messages",
            params={"$top": top},
        )
        _raise_for_status(r)
        data = r.json()
    return {"messages": data.get("value", []), "count": len(data.get("value", []))}


# ─── List members ─────────────────────────────────────────────────────────────

@register_node("teams.list_members")
async def teams_list_members(config: dict, input_data: dict, credential_id: str, db) -> dict:
    team_id = config.get("team_id") or input_data.get("team_id")
    if not team_id:
        raise ValueError("teams.list_members requires 'team_id'")

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/teams/{team_id}/members")
        _raise_for_status(r)
        data = r.json()
    return {"members": data.get("value", []), "count": len(data.get("value", []))}


# ─── Add member ───────────────────────────────────────────────────────────────

@register_node("teams.add_member")
async def teams_add_member(config: dict, input_data: dict, credential_id: str, db) -> dict:
    team_id = config.get("team_id") or input_data.get("team_id")
    user_id = config.get("user_id") or input_data.get("user_id")

    if not team_id:
        raise ValueError("teams.add_member requires 'team_id'")
    if not user_id:
        raise ValueError("teams.add_member requires 'user_id'")

    async with await _client(credential_id, db) as client:
        # If user_id looks like an email, resolve it to an object ID first
        if "@" in user_id:
            r = await client.get(f"/users/{user_id}")
            _raise_for_status(r)
            user_id = r.json().get("id", user_id)

        payload = {
            "@odata.type": "#microsoft.graph.aadUserConversationMember",
            "roles": [],
            "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{user_id}')",
        }
        r = await client.post(f"/teams/{team_id}/members", content=json.dumps(payload))
        _raise_for_status(r)
        return r.json()


# ─── Create online meeting ────────────────────────────────────────────────────

@register_node("teams.create_meeting")
async def teams_create_meeting(config: dict, input_data: dict, credential_id: str, db) -> dict:
    subject = config.get("subject") or input_data.get("subject", "New Meeting")
    start_datetime = config.get("start_datetime") or input_data.get("start_datetime")
    end_datetime = config.get("end_datetime") or input_data.get("end_datetime")
    attendees = config.get("attendees") or input_data.get("attendees", [])

    if not start_datetime:
        raise ValueError("teams.create_meeting requires 'start_datetime'")
    if not end_datetime:
        raise ValueError("teams.create_meeting requires 'end_datetime'")

    payload: dict = {
        "subject": subject,
        "startDateTime": start_datetime,
        "endDateTime": end_datetime,
    }

    if attendees:
        payload["participants"] = {
            "attendees": [
                {
                    "upn": email,
                    "role": "attendee",
                    "identity": {
                        "user": {"displayName": email}
                    },
                }
                for email in attendees
            ]
        }

    async with await _client(credential_id, db) as client:
        r = await client.post("/me/onlineMeetings", content=json.dumps(payload))
        _raise_for_status(r)
        data = r.json()

    return {
        "id": data.get("id"),
        "join_url": data.get("joinWebUrl"),
        "subject": data.get("subject"),
        "start_datetime": data.get("startDateTime"),
        "end_datetime": data.get("endDateTime"),
    }


# ─── Send adaptive card ───────────────────────────────────────────────────────

@register_node("teams.send_adaptive_card")
async def teams_send_adaptive_card(config: dict, input_data: dict, credential_id: str, db) -> dict:
    team_id = config.get("team_id") or input_data.get("team_id")
    channel_id = config.get("channel_id") or input_data.get("channel_id")
    card_json = config.get("card_json") or input_data.get("card_json")

    if not team_id:
        raise ValueError("teams.send_adaptive_card requires 'team_id'")
    if not channel_id:
        raise ValueError("teams.send_adaptive_card requires 'channel_id'")
    if not card_json:
        raise ValueError("teams.send_adaptive_card requires 'card_json'")

    # card_json may be a dict or a JSON string
    if isinstance(card_json, str):
        card_json = json.loads(card_json)

    payload = {
        "body": {
            "contentType": "html",
            "content": "<attachment id=\"adaptiveCard\"></attachment>",
        },
        "attachments": [
            {
                "id": "adaptiveCard",
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": json.dumps(card_json),
            }
        ],
    }

    async with await _client(credential_id, db) as client:
        r = await client.post(
            f"/teams/{team_id}/channels/{channel_id}/messages",
            content=json.dumps(payload),
        )
        _raise_for_status(r)
        return r.json()


# ─── Get user ─────────────────────────────────────────────────────────────────

@register_node("teams.get_user")
async def teams_get_user(config: dict, input_data: dict, credential_id: str, db) -> dict:
    user_id = config.get("user_id") or input_data.get("user_id")
    if not user_id:
        raise ValueError("teams.get_user requires 'user_id'")

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/users/{user_id}")
        _raise_for_status(r)
        return r.json()


# ─── Send direct message (1:1 chat) ──────────────────────────────────────────

@register_node("teams.send_direct_message")
async def teams_send_direct_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    to_user_id = config.get("to_user_id") or input_data.get("to_user_id")
    content = config.get("content") or input_data.get("content", "")
    content_type = config.get("content_type", "text")

    if not to_user_id:
        raise ValueError("teams.send_direct_message requires 'to_user_id'")

    async with await _client(credential_id, db) as client:
        # If the ID looks like an email, resolve to object ID
        if "@" in to_user_id:
            r = await client.get(f"/users/{to_user_id}")
            _raise_for_status(r)
            to_user_id = r.json().get("id", to_user_id)

        # Get the current user (me)
        me_r = await client.get("/me")
        _raise_for_status(me_r)
        my_id = me_r.json().get("id")

        # Create or retrieve existing 1:1 chat
        chat_payload = {
            "chatType": "oneOnOne",
            "members": [
                {
                    "@odata.type": "#microsoft.graph.aadUserConversationMember",
                    "roles": ["owner"],
                    "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{my_id}')",
                },
                {
                    "@odata.type": "#microsoft.graph.aadUserConversationMember",
                    "roles": ["owner"],
                    "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{to_user_id}')",
                },
            ],
        }
        chat_r = await client.post("/chats", content=json.dumps(chat_payload))
        _raise_for_status(chat_r)
        chat_id = chat_r.json().get("id")

        # Send message to chat
        msg_payload = {
            "body": {
                "contentType": content_type,
                "content": content,
            }
        }
        msg_r = await client.post(f"/chats/{chat_id}/messages", content=json.dumps(msg_payload))
        _raise_for_status(msg_r)
        result = msg_r.json()
        result["chat_id"] = chat_id
        return result
