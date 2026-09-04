"""
MessageBird messaging integration.

Credential fields:
  - api_key: MessageBird API key (sent as Authorization: AccessKey header)

Base URL: https://rest.messagebird.com
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://rest.messagebird.com"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("MessageBird credential is missing 'api_key'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "Authorization": f"AccessKey {api_key}",
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
        raise ValueError(f"MessageBird API error {r.status_code}: {detail}")
    if not r.content:
        return {}
    return r.json()


# ---------------------------------------------------------------------------
# SMS
# ---------------------------------------------------------------------------

@register_node("messagebird.send_sms")
async def messagebird_send_sms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /messages — send an SMS message."""
    originator = config.get("originator") if config.get("originator") is not None else input_data.get("originator")
    recipients = config.get("recipients") if config.get("recipients") is not None else input_data.get("recipients")
    body_text = config.get("body") if config.get("body") is not None else input_data.get("body")
    if not originator or not recipients or not body_text:
        raise ValueError("messagebird.send_sms requires 'originator', 'recipients', and 'body'")
    body: dict = {
        "originator": originator,
        "recipients": recipients if isinstance(recipients, list) else [recipients],
        "body": body_text,
    }
    reference = config.get("reference") if config.get("reference") is not None else input_data.get("reference")
    if reference is not None:
        body["reference"] = reference
    scheduled_datetime = config.get("scheduledDatetime") if config.get("scheduledDatetime") is not None else input_data.get("scheduledDatetime")
    if scheduled_datetime is not None:
        body["scheduledDatetime"] = scheduled_datetime
    type_ = config.get("type") if config.get("type") is not None else input_data.get("type")
    if type_ is not None:
        body["type"] = type_
    async with await _client(credential_id, db) as client:
        r = await client.post("/messages", json=body)
    return _check(r)


@register_node("messagebird.get_message")
async def messagebird_get_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /messages/{id} — retrieve a specific message."""
    message_id = config.get("message_id") if config.get("message_id") is not None else input_data.get("message_id")
    if not message_id:
        raise ValueError("messagebird.get_message requires 'message_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/messages/{message_id}")
    return _check(r)


@register_node("messagebird.list_messages")
async def messagebird_list_messages(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /messages — list SMS messages."""
    params: dict = {}
    limit = config.get("limit") if config.get("limit") is not None else input_data.get("limit")
    if limit is not None:
        params["limit"] = int(limit)
    offset = config.get("offset") if config.get("offset") is not None else input_data.get("offset")
    if offset is not None:
        params["offset"] = int(offset)
    status = config.get("status") if config.get("status") is not None else input_data.get("status")
    if status is not None:
        params["status"] = status
    async with await _client(credential_id, db) as client:
        r = await client.get("/messages", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Voice
# ---------------------------------------------------------------------------

@register_node("messagebird.send_voice_message")
async def messagebird_send_voice_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /voicemessages — send a text-to-speech voice message."""
    originator = config.get("originator") if config.get("originator") is not None else input_data.get("originator")
    recipients = config.get("recipients") if config.get("recipients") is not None else input_data.get("recipients")
    body_text = config.get("body") if config.get("body") is not None else input_data.get("body")
    if not originator or not recipients or not body_text:
        raise ValueError("messagebird.send_voice_message requires 'originator', 'recipients', and 'body'")
    body: dict = {
        "originator": originator,
        "recipients": recipients if isinstance(recipients, list) else [recipients],
        "body": body_text,
    }
    language = config.get("language") if config.get("language") is not None else input_data.get("language")
    if language is not None:
        body["language"] = language
    voice = config.get("voice") if config.get("voice") is not None else input_data.get("voice")
    if voice is not None:
        body["voice"] = voice
    repeat = config.get("repeat") if config.get("repeat") is not None else input_data.get("repeat")
    if repeat is not None:
        body["repeat"] = int(repeat)
    async with await _client(credential_id, db) as client:
        r = await client.post("/voicemessages", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

@register_node("messagebird.create_conversation")
async def messagebird_create_conversation(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /conversations/start — start a new conversation."""
    to = config.get("to") if config.get("to") is not None else input_data.get("to")
    channel_id = config.get("channelId") if config.get("channelId") is not None else input_data.get("channelId")
    content = config.get("content") if config.get("content") is not None else input_data.get("content")
    if not to or not channel_id or not content:
        raise ValueError("messagebird.create_conversation requires 'to', 'channelId', and 'content'")
    body: dict = {"to": to, "channelId": channel_id, "content": content}
    type_ = config.get("type") if config.get("type") is not None else input_data.get("type")
    if type_ is not None:
        body["type"] = type_
    async with await _client(credential_id, db) as client:
        r = await client.post("/conversations/start", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

@register_node("messagebird.list_contacts")
async def messagebird_list_contacts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /contacts — list contacts."""
    params: dict = {}
    limit = config.get("limit") if config.get("limit") is not None else input_data.get("limit")
    if limit is not None:
        params["limit"] = int(limit)
    offset = config.get("offset") if config.get("offset") is not None else input_data.get("offset")
    if offset is not None:
        params["offset"] = int(offset)
    async with await _client(credential_id, db) as client:
        r = await client.get("/contacts", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Phone number lookup
# ---------------------------------------------------------------------------

@register_node("messagebird.lookup_phone_number")
async def messagebird_lookup_phone_number(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /lookup/{phoneNumber} — look up information about a phone number."""
    phone_number = config.get("phoneNumber") if config.get("phoneNumber") is not None else input_data.get("phoneNumber")
    if not phone_number:
        raise ValueError("messagebird.lookup_phone_number requires 'phoneNumber'")
    params: dict = {}
    country_code = config.get("countryCode") if config.get("countryCode") is not None else input_data.get("countryCode")
    if country_code is not None:
        params["countryCode"] = country_code
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/lookup/{phone_number}", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(creds: dict) -> None:
    """Test MessageBird credentials by fetching the account balance."""
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Missing 'api_key'")
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        headers={"Authorization": f"AccessKey {api_key}", "Accept": "application/json"},
        timeout=15.0,
    ) as client:
        r = await client.get("/balance")
    if not r.is_success:
        raise ValueError(f"MessageBird connection failed: {r.status_code} {r.text}")
