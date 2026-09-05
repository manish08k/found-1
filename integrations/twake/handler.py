"""Twake team collaboration integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

TWAKE_BASE = "https://api.twake.app"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@register_node("twake.send_message")
async def send_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a direct message in Twake.

    config/input_data:
      token      — Bearer token (required)
      channel_id — channel/conversation ID (required)
      message    — message text (required)
    """
    merged = {**config, **input_data}
    token = merged.get("token") or ""
    channel_id = merged.get("channel_id") or ""
    message = merged.get("message") or ""

    if not token:
        raise ValueError("token is required for twake.send_message")
    if not channel_id:
        raise ValueError("channel_id is required for twake.send_message")
    if not message:
        raise ValueError("message is required for twake.send_message")

    payload = {"channel_id": channel_id, "content": {"formatted": message}}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{TWAKE_BASE}/api/v1/direct/push", json=payload, headers=_headers(token))
        r.raise_for_status()
        data = r.json()

    log.info("twake.send_message", channel_id=channel_id)
    return {"message": data, "channel_id": channel_id}


@register_node("twake.get_channel_messages")
async def get_channel_messages(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get messages from a Twake direct channel.

    config/input_data:
      token      — Bearer token (required)
      channel_id — channel ID (required)
      limit      — max messages to return (default 50)
    """
    merged = {**config, **input_data}
    token = merged.get("token") or ""
    channel_id = merged.get("channel_id") or ""
    limit = int(merged.get("limit", 50))

    if not token:
        raise ValueError("token is required for twake.get_channel_messages")
    if not channel_id:
        raise ValueError("channel_id is required for twake.get_channel_messages")

    params = {"channel_id": channel_id, "limit": limit}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{TWAKE_BASE}/api/v1/direct/list", headers=_headers(token), params=params)
        r.raise_for_status()
        data = r.json()

    messages = data if isinstance(data, list) else data.get("messages", data)
    log.info("twake.get_channel_messages", channel_id=channel_id, count=len(messages) if isinstance(messages, list) else 0)
    return {"messages": messages, "channel_id": channel_id}


@register_node("twake.list_channels")
async def list_channels(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List channels in a Twake workspace.

    config/input_data:
      token        — Bearer token (required)
      workspace_id — workspace ID (required)
    """
    merged = {**config, **input_data}
    token = merged.get("token") or ""
    workspace_id = merged.get("workspace_id") or ""

    if not token:
        raise ValueError("token is required for twake.list_channels")
    if not workspace_id:
        raise ValueError("workspace_id is required for twake.list_channels")

    params = {"workspace_id": workspace_id}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{TWAKE_BASE}/api/v1/channels/list", headers=_headers(token), params=params)
        r.raise_for_status()
        data = r.json()

    channels = data if isinstance(data, list) else data.get("channels", data)
    log.info("twake.list_channels", workspace_id=workspace_id, count=len(channels) if isinstance(channels, list) else 0)
    return {"channels": channels, "workspace_id": workspace_id}


@register_node("twake.list_workspaces")
async def list_workspaces(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all accessible Twake workspaces.

    config/input_data:
      token — Bearer token (required)
    """
    merged = {**config, **input_data}
    token = merged.get("token") or ""

    if not token:
        raise ValueError("token is required for twake.list_workspaces")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{TWAKE_BASE}/api/v1/workspaces/list", headers=_headers(token))
        r.raise_for_status()
        data = r.json()

    workspaces = data if isinstance(data, list) else data.get("workspaces", data)
    log.info("twake.list_workspaces", count=len(workspaces) if isinstance(workspaces, list) else 0)
    return {"workspaces": workspaces}
