"""Twist async communication integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

TWIST_BASE = "https://api.twist.com/api/v3"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@register_node("twist.get_workspaces")
async def get_workspaces(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get all workspaces for the authenticated user.

    config/input_data:
      token — Bearer token (required)
    """
    merged = {**config, **input_data}
    token = merged.get("token") or ""

    if not token:
        raise ValueError("token is required for twist.get_workspaces")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{TWIST_BASE}/workspaces/get", headers=_headers(token))
        r.raise_for_status()
        data = r.json()

    workspaces = data if isinstance(data, list) else data.get("workspaces", data)
    log.info("twist.get_workspaces", count=len(workspaces) if isinstance(workspaces, list) else 0)
    return {"workspaces": workspaces}


@register_node("twist.get_channels")
async def get_channels(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get channels in a Twist workspace.

    config/input_data:
      token        — Bearer token (required)
      workspace_id — workspace ID (required)
    """
    merged = {**config, **input_data}
    token = merged.get("token") or ""
    workspace_id = merged.get("workspace_id") or ""

    if not token:
        raise ValueError("token is required for twist.get_channels")
    if not workspace_id:
        raise ValueError("workspace_id is required for twist.get_channels")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{TWIST_BASE}/channels/get",
            headers=_headers(token),
            params={"workspace_id": workspace_id},
        )
        r.raise_for_status()
        data = r.json()

    channels = data if isinstance(data, list) else data.get("channels", data)
    log.info("twist.get_channels", workspace_id=workspace_id, count=len(channels) if isinstance(channels, list) else 0)
    return {"channels": channels, "workspace_id": workspace_id}


@register_node("twist.create_message")
async def create_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Post a message to a Twist channel.

    config/input_data:
      token      — Bearer token (required)
      channel_id — channel ID (required)
      content    — message content (required)
    """
    merged = {**config, **input_data}
    token = merged.get("token") or ""
    channel_id = merged.get("channel_id") or ""
    content = merged.get("content") or ""

    if not token:
        raise ValueError("token is required for twist.create_message")
    if not channel_id:
        raise ValueError("channel_id is required for twist.create_message")
    if not content:
        raise ValueError("content is required for twist.create_message")

    payload = {"channel_id": channel_id, "content": content}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{TWIST_BASE}/messages/add", json=payload, headers=_headers(token))
        r.raise_for_status()
        data = r.json()

    log.info("twist.create_message", channel_id=channel_id)
    return {"message": data, "id": data.get("id")}


@register_node("twist.get_messages")
async def get_messages(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get messages from a Twist channel.

    config/input_data:
      token      — Bearer token (required)
      channel_id — channel ID (required)
    """
    merged = {**config, **input_data}
    token = merged.get("token") or ""
    channel_id = merged.get("channel_id") or ""

    if not token:
        raise ValueError("token is required for twist.get_messages")
    if not channel_id:
        raise ValueError("channel_id is required for twist.get_messages")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{TWIST_BASE}/messages/get",
            headers=_headers(token),
            params={"channel_id": channel_id},
        )
        r.raise_for_status()
        data = r.json()

    messages = data if isinstance(data, list) else data.get("messages", data)
    log.info("twist.get_messages", channel_id=channel_id, count=len(messages) if isinstance(messages, list) else 0)
    return {"messages": messages, "channel_id": channel_id}


@register_node("twist.add_comment")
async def add_comment(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Add a comment to a Twist thread.

    config/input_data:
      token     — Bearer token (required)
      thread_id — thread ID (required)
      content   — comment content (required)
    """
    merged = {**config, **input_data}
    token = merged.get("token") or ""
    thread_id = merged.get("thread_id") or ""
    content = merged.get("content") or ""

    if not token:
        raise ValueError("token is required for twist.add_comment")
    if not thread_id:
        raise ValueError("thread_id is required for twist.add_comment")
    if not content:
        raise ValueError("content is required for twist.add_comment")

    payload = {"thread_id": thread_id, "content": content}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{TWIST_BASE}/comments/add", json=payload, headers=_headers(token))
        r.raise_for_status()
        data = r.json()

    log.info("twist.add_comment", thread_id=thread_id)
    return {"comment": data, "id": data.get("id")}
