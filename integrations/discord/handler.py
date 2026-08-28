"""Discord integration — messages, channels, roles, webhooks + polling."""
import structlog
import httpx

from core.execution_engine import register_node
from triggers.engine import register_poller
from oauth.flow import get_access_token

log = structlog.get_logger(__name__)

DISCORD_BASE = "https://discord.com/api/v10"


async def _discord(credential_id: str, db) -> httpx.AsyncClient:
    token = await get_access_token(credential_id, db)
    return httpx.AsyncClient(
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30,
    )


async def _bot_client() -> httpx.AsyncClient:
    from core.config import settings
    return httpx.AsyncClient(
        headers={"Authorization": f"Bot {settings.DISCORD_BOT_TOKEN}", "Content-Type": "application/json"},
        timeout=30,
    )


@register_node("discord.send_message")
async def discord_send_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    channel_id = config.get("channel_id") or input_data.get("channel_id")
    content = config.get("content") or input_data.get("content", "")
    embeds = config.get("embeds") or input_data.get("embeds", [])
    tts = config.get("tts", False)

    payload = {"content": content, "tts": tts}
    if embeds:
        payload["embeds"] = embeds

    async with await _bot_client() as client:
        r = await client.post(f"{DISCORD_BASE}/channels/{channel_id}/messages", json=payload)
        r.raise_for_status()
        data = r.json()
    return {"message_id": data["id"], "channel_id": channel_id}


@register_node("discord.send_embed")
async def discord_send_embed(config: dict, input_data: dict, credential_id: str, db) -> dict:
    channel_id = config.get("channel_id") or input_data.get("channel_id")
    title = config.get("title") or input_data.get("title", "")
    description = config.get("description") or input_data.get("description", "")
    color = config.get("color", 0x5865F2)
    fields = config.get("fields") or input_data.get("fields", [])
    footer = config.get("footer")
    image = config.get("image")

    embed = {"title": title, "description": description, "color": color, "fields": fields}
    if footer:
        embed["footer"] = footer
    if image:
        embed["image"] = {"url": image}

    async with await _bot_client() as client:
        r = await client.post(f"{DISCORD_BASE}/channels/{channel_id}/messages",
                              json={"embeds": [embed]})
        r.raise_for_status()
        data = r.json()
    return {"message_id": data["id"]}


@register_node("discord.edit_message")
async def discord_edit_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    channel_id = config.get("channel_id") or input_data.get("channel_id")
    message_id = config.get("message_id") or input_data.get("message_id")
    content = config.get("content") or input_data.get("content", "")

    async with await _bot_client() as client:
        r = await client.patch(f"{DISCORD_BASE}/channels/{channel_id}/messages/{message_id}",
                               json={"content": content})
        r.raise_for_status()
        data = r.json()
    return {"message_id": data["id"]}


@register_node("discord.delete_message")
async def discord_delete_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    channel_id = config.get("channel_id") or input_data.get("channel_id")
    message_id = config.get("message_id") or input_data.get("message_id")

    async with await _bot_client() as client:
        r = await client.delete(f"{DISCORD_BASE}/channels/{channel_id}/messages/{message_id}")
        r.raise_for_status()
    return {"ok": True}


@register_node("discord.add_reaction")
async def discord_add_reaction(config: dict, input_data: dict, credential_id: str, db) -> dict:
    channel_id = config.get("channel_id") or input_data.get("channel_id")
    message_id = config.get("message_id") or input_data.get("message_id")
    emoji = config.get("emoji") or input_data.get("emoji", "👍")

    async with await _bot_client() as client:
        r = await client.put(
            f"{DISCORD_BASE}/channels/{channel_id}/messages/{message_id}/reactions/{emoji}/@me"
        )
        r.raise_for_status()
    return {"ok": True}


@register_node("discord.create_channel")
async def discord_create_channel(config: dict, input_data: dict, credential_id: str, db) -> dict:
    guild_id = config.get("guild_id") or input_data.get("guild_id")
    name = config.get("name") or input_data.get("name")
    channel_type = config.get("type", 0)  # 0=text, 2=voice, 4=category
    topic = config.get("topic", "")

    async with await _bot_client() as client:
        r = await client.post(f"{DISCORD_BASE}/guilds/{guild_id}/channels",
                              json={"name": name, "type": channel_type, "topic": topic})
        r.raise_for_status()
        data = r.json()
    return {"channel_id": data["id"], "name": data["name"]}


@register_node("discord.assign_role")
async def discord_assign_role(config: dict, input_data: dict, credential_id: str, db) -> dict:
    guild_id = config.get("guild_id") or input_data.get("guild_id")
    user_id = config.get("user_id") or input_data.get("user_id")
    role_id = config.get("role_id") or input_data.get("role_id")

    async with await _bot_client() as client:
        r = await client.put(f"{DISCORD_BASE}/guilds/{guild_id}/members/{user_id}/roles/{role_id}")
        r.raise_for_status()
    return {"ok": True}


@register_node("discord.kick_member")
async def discord_kick_member(config: dict, input_data: dict, credential_id: str, db) -> dict:
    guild_id = config.get("guild_id") or input_data.get("guild_id")
    user_id = config.get("user_id") or input_data.get("user_id")

    async with await _bot_client() as client:
        r = await client.delete(f"{DISCORD_BASE}/guilds/{guild_id}/members/{user_id}")
        r.raise_for_status()
    return {"ok": True}


@register_node("discord.get_guild_members")
async def discord_get_members(config: dict, input_data: dict, credential_id: str, db) -> dict:
    guild_id = config.get("guild_id") or input_data.get("guild_id")
    limit = config.get("limit", 100)

    async with await _bot_client() as client:
        r = await client.get(f"{DISCORD_BASE}/guilds/{guild_id}/members", params={"limit": limit})
        r.raise_for_status()
        members = r.json()
    return {"members": [{"id": m["user"]["id"], "username": m["user"]["username"]} for m in members]}


# ─── Polling ──────────────────────────────────────────────────────────────────

_discord_seen: dict[str, str] = {}


@register_poller("discord", "new_message")
async def poll_discord_messages(config: dict, credential_id: str, db) -> list[dict]:
    channel_id = config.get("channel_id")
    key = f"{credential_id}:{channel_id}"
    after = _discord_seen.get(key)

    try:
        params = {"limit": 20}
        if after:
            params["after"] = after

        async with await _bot_client() as client:
            r = await client.get(f"{DISCORD_BASE}/channels/{channel_id}/messages", params=params)
            r.raise_for_status()
            messages = r.json()

        if messages:
            _discord_seen[key] = messages[0]["id"]
        return [{"id": m["id"], "content": m["content"],
                 "author": m["author"]["username"], "timestamp": m["timestamp"]}
                for m in reversed(messages)]
    except Exception as e:
        log.error("discord_poll_error", error=str(e))
        return []
