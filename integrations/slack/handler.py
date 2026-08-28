"""Slack integration — node handlers + polling triggers."""
import structlog
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

from core.execution_engine import register_node
from triggers.engine import register_poller
from oauth.flow import get_access_token

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> AsyncWebClient:
    token = await get_access_token(credential_id, db)
    return AsyncWebClient(token=token)


@register_node("slack.send_message")
async def slack_send_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    client = await _client(credential_id, db)
    channel = config.get("channel") or input_data.get("channel")
    text = config.get("text") or input_data.get("text", "")
    blocks = config.get("blocks") or input_data.get("blocks")

    kwargs = {"channel": channel, "text": text}
    if blocks:
        kwargs["blocks"] = blocks

    response = await client.chat_postMessage(**kwargs)
    return {"ts": response["ts"], "channel": response["channel"]}


@register_node("slack.send_dm")
async def slack_send_dm(config: dict, input_data: dict, credential_id: str, db) -> dict:
    client = await _client(credential_id, db)
    user_email = config.get("user_email") or input_data.get("user_email")
    text = config.get("text") or input_data.get("text", "")

    # Lookup user by email
    user_resp = await client.users_lookupByEmail(email=user_email)
    user_id = user_resp["user"]["id"]

    # Open DM channel
    dm_resp = await client.conversations_open(users=user_id)
    channel = dm_resp["channel"]["id"]

    response = await client.chat_postMessage(channel=channel, text=text)
    return {"ts": response["ts"], "channel": channel, "user_id": user_id}


@register_node("slack.get_messages")
async def slack_get_messages(config: dict, input_data: dict, credential_id: str, db) -> dict:
    client = await _client(credential_id, db)
    channel = config.get("channel") or input_data.get("channel")
    limit = config.get("limit", 10)

    response = await client.conversations_history(channel=channel, limit=limit)
    return {"messages": response["messages"]}


@register_node("slack.create_channel")
async def slack_create_channel(config: dict, input_data: dict, credential_id: str, db) -> dict:
    client = await _client(credential_id, db)
    name = config.get("name") or input_data.get("name")
    is_private = config.get("is_private", False)

    response = await client.conversations_create(name=name, is_private=is_private)
    return {"channel_id": response["channel"]["id"], "name": response["channel"]["name"]}


@register_node("slack.invite_to_channel")
async def slack_invite_to_channel(config: dict, input_data: dict, credential_id: str, db) -> dict:
    client = await _client(credential_id, db)
    channel = config.get("channel") or input_data.get("channel")
    users = config.get("users") or input_data.get("users")  # comma-separated user IDs

    response = await client.conversations_invite(channel=channel, users=users)
    return {"channel": response["channel"]["id"]}


@register_node("slack.upload_file")
async def slack_upload_file(config: dict, input_data: dict, credential_id: str, db) -> dict:
    client = await _client(credential_id, db)
    channel = config.get("channel") or input_data.get("channel")
    content = config.get("content") or input_data.get("content", "")
    filename = config.get("filename", "file.txt")
    title = config.get("title", filename)

    response = await client.files_upload_v2(
        channel=channel,
        content=content,
        filename=filename,
        title=title,
    )
    return {"file_id": response["file"]["id"], "permalink": response["file"].get("permalink")}


@register_node("slack.add_reaction")
async def slack_add_reaction(config: dict, input_data: dict, credential_id: str, db) -> dict:
    client = await _client(credential_id, db)
    channel = config.get("channel") or input_data.get("channel")
    timestamp = config.get("ts") or input_data.get("ts")
    name = config.get("reaction", "white_check_mark")

    await client.reactions_add(channel=channel, timestamp=timestamp, name=name)
    return {"ok": True}


@register_node("slack.get_user_info")
async def slack_get_user_info(config: dict, input_data: dict, credential_id: str, db) -> dict:
    client = await _client(credential_id, db)
    user_id = config.get("user_id") or input_data.get("user_id")
    email = config.get("email") or input_data.get("email")

    if email:
        response = await client.users_lookupByEmail(email=email)
        user = response["user"]
    else:
        response = await client.users_info(user=user_id)
        user = response["user"]

    return {
        "id": user["id"],
        "name": user.get("real_name"),
        "email": user.get("profile", {}).get("email"),
        "title": user.get("profile", {}).get("title"),
    }


# ─── Polling trigger: new messages in channel ─────────────────────────────────

_slack_last_ts: dict[str, str] = {}


@register_poller("slack", "new_message")
async def poll_slack_messages(config: dict, credential_id: str, db) -> list[dict]:
    client = await _client(credential_id, db)
    channel = config.get("channel")
    if not channel:
        return []

    key = f"{credential_id}:{channel}"
    oldest = _slack_last_ts.get(key, "0")

    try:
        response = await client.conversations_history(channel=channel, oldest=oldest, limit=50)
        messages = response.get("messages", [])
        if messages:
            _slack_last_ts[key] = messages[0]["ts"]
        return [{"channel": channel, **m} for m in reversed(messages)]
    except SlackApiError as e:
        log.error("slack_poll_error", error=str(e))
        return []
