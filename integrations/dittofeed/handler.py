"""Dittofeed customer engagement platform — handler for dittofeed integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://app.dittofeed.com/api/v1"


@register_node("dittofeed.identify_user")
async def dittofeed_identify_user(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Identify a user.

    config/input_data:
      api_key — API key or token (required)
      user_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    user_id = merged.get("user_id") or ""
    if not user_id:
        raise ValueError("user_id required for dittofeed.identify_user")
    payload = {"user_id": user_id}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/identify", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("dittofeed.identify_user")
    return {"data": data}

@register_node("dittofeed.track_event")
async def dittofeed_track_event(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Track an event.

    config/input_data:
      api_key — API key or token (required)
      user_id — (required)
      event — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    user_id = merged.get("user_id") or ""
    event = merged.get("event") or ""
    if not user_id or not event:
        raise ValueError("user_id, event required for dittofeed.track_event")
    payload = {"user_id": user_id, "event": event}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/track", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("dittofeed.track_event")
    return {"data": data}

@register_node("dittofeed.send_message")
async def dittofeed_send_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a message.

    config/input_data:
      api_key — API key or token (required)
      user_id — (required)
      channel — (required)
      body — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    user_id = merged.get("user_id") or ""
    channel = merged.get("channel") or ""
    body = merged.get("body") or ""
    if not user_id or not channel or not body:
        raise ValueError("user_id, channel, body required for dittofeed.send_message")
    payload = {"user_id": user_id, "channel": channel, "body": body}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/messages", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("dittofeed.send_message")
    return {"data": data}
