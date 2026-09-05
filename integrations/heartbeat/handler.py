"""Heartbeat — community platform integration."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

HEARTBEAT_BASE = "https://api.heartbeat.chat/v0"


def _headers(config: dict) -> dict:
    api_key = config.get("api_key", "")
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


@register_node("heartbeat.list_channels")
async def heartbeat_list_channels(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List channels in a Heartbeat community.

    config:
      api_key — Heartbeat API key
    """
    async with httpx.AsyncClient(base_url=HEARTBEAT_BASE, timeout=30) as client:
        r = await client.get("/channels", headers=_headers(config))
        r.raise_for_status()
        data = r.json()

    channels = data.get("channels", data if isinstance(data, list) else [])
    log.info("heartbeat.list_channels", count=len(channels))
    return {"channels": channels, "count": len(channels)}


@register_node("heartbeat.send_message")
async def heartbeat_send_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a message to a Heartbeat channel.

    config/input_data:
      api_key    — Heartbeat API key
      channel_id — channel ID to post into (required)
      text       — message content (required)
    """
    channel_id = config.get("channel_id") or input_data.get("channel_id")
    text = config.get("text") or input_data.get("text")

    if not channel_id:
        raise ValueError("channel_id is required for heartbeat.send_message")
    if not text:
        raise ValueError("text is required for heartbeat.send_message")

    async with httpx.AsyncClient(base_url=HEARTBEAT_BASE, timeout=30) as client:
        r = await client.post(
            f"/channels/{channel_id}/messages",
            json={"content": text},
            headers=_headers(config),
        )
        r.raise_for_status()
        result = r.json()

    log.info("heartbeat.send_message", channel_id=channel_id)
    return {"message": result, "channel_id": channel_id}


@register_node("heartbeat.list_members")
async def heartbeat_list_members(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List members of a Heartbeat community.

    config:
      api_key — Heartbeat API key
    """
    async with httpx.AsyncClient(base_url=HEARTBEAT_BASE, timeout=30) as client:
        r = await client.get("/members", headers=_headers(config))
        r.raise_for_status()
        data = r.json()

    members = data.get("members", data if isinstance(data, list) else [])
    log.info("heartbeat.list_members", count=len(members))
    return {"members": members, "count": len(members)}
