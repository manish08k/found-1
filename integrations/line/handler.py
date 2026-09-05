"""
LINE messaging platform integration.

Provides message sending, profile retrieval, and reply operations via the LINE Messaging API.

Credential fields:
  - channel_access_token : LINE Channel Access Token (Bearer auth)
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.line.me/v2/bot"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    channel_access_token = creds.get("channel_access_token")
    if not channel_access_token:
        raise ValueError("LINE credential missing 'channel_access_token'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Bearer {channel_access_token}",
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
        raise ValueError(f"LINE API error {r.status_code}: {detail}")


def _build_message(message_type: str, text: str, extra: dict) -> dict:
    """Build a LINE message object."""
    if message_type == "text":
        return {"type": "text", "text": text}
    elif message_type == "sticker":
        return {
            "type": "sticker",
            "packageId": extra.get("package_id", "1"),
            "stickerId": extra.get("sticker_id", "1"),
        }
    # Default to text
    return {"type": "text", "text": text}


@register_node("line.send_message")
async def line_send_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Send a message to a LINE user (push message)."""
    to = config.get("to") or input_data.get("to")
    text = config.get("text") or input_data.get("text", "")
    message_type = config.get("message_type") or input_data.get("message_type", "text")

    if not to:
        raise ValueError("line.send_message requires 'to' (user/group/room ID)")
    if not text:
        raise ValueError("line.send_message requires 'text'")

    message = _build_message(message_type, text, {**config, **input_data})
    payload = {"to": to, "messages": [message]}

    log.info("line.send_message", to=to, message_type=message_type)
    async with await _client(credential_id, db) as client:
        r = await client.post("/message/push", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"sent": True, "to": to, "response": data}


@register_node("line.get_profile")
async def line_get_profile(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Get a LINE user's profile information."""
    user_id = config.get("user_id") or input_data.get("user_id")
    if not user_id:
        raise ValueError("line.get_profile requires 'user_id'")

    log.info("line.get_profile", user_id=user_id)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/profile/{user_id}")
        _raise_for_status(r)
        profile = r.json()

    return {"profile": profile}


@register_node("line.push_message")
async def line_push_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Push one or more messages to a LINE user, group, or room."""
    to = config.get("to") or input_data.get("to")
    messages = config.get("messages") or input_data.get("messages")
    text = config.get("text") or input_data.get("text")

    if not to:
        raise ValueError("line.push_message requires 'to'")

    if not messages:
        if not text:
            raise ValueError("line.push_message requires 'messages' list or 'text'")
        messages = [{"type": "text", "text": text}]

    if len(messages) > 5:
        raise ValueError("LINE push_message supports a maximum of 5 messages per request")

    payload = {"to": to, "messages": messages}

    log.info("line.push_message", to=to, message_count=len(messages))
    async with await _client(credential_id, db) as client:
        r = await client.post("/message/push", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"sent": True, "to": to, "message_count": len(messages), "response": data}


@register_node("line.reply_message")
async def line_reply_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Reply to a LINE message using a reply token."""
    reply_token = config.get("reply_token") or input_data.get("reply_token")
    messages = config.get("messages") or input_data.get("messages")
    text = config.get("text") or input_data.get("text")

    if not reply_token:
        raise ValueError("line.reply_message requires 'reply_token'")

    if not messages:
        if not text:
            raise ValueError("line.reply_message requires 'messages' list or 'text'")
        messages = [{"type": "text", "text": text}]

    if len(messages) > 5:
        raise ValueError("LINE reply_message supports a maximum of 5 messages per request")

    payload = {"replyToken": reply_token, "messages": messages}

    log.info("line.reply_message", message_count=len(messages))
    async with await _client(credential_id, db) as client:
        r = await client.post("/message/reply", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"replied": True, "message_count": len(messages), "response": data}
