"""Anyhook WebSocket webhook service — handler for anyhook_websocket integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.anyhook.io/v1"


@register_node("anyhook_websocket.list_channels")
async def anyhook_websocket_list_channels(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List WebSocket channels.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/channels", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("anyhook_websocket.list_channels")
    return {"data": data}

@register_node("anyhook_websocket.send_message")
async def anyhook_websocket_send_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a message to a channel.

    config/input_data:
      api_key — API key or token (required)
      channel_id — (required)
      message — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    channel_id = merged.get("channel_id") or ""
    message = merged.get("message") or ""
    if not channel_id or not message:
        raise ValueError("channel_id, message required for anyhook_websocket.send_message")
    payload = merged
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/channels/{channel_id}/messages", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("anyhook_websocket.send_message")
    return {"data": data}
