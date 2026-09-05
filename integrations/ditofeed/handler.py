"""Dittofeed integration — customer messaging via Dittofeed API v1."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

DITOFEED_BASE = "https://app.dittofeed.com/api/public/v1"


def _headers(config: dict, input_data: dict) -> dict:
    merged = {**config, **input_data}
    return {"Authorization": f"Bearer {merged.get('api_key', '')}"}


@register_node("ditofeed.identify_user")
async def identify_user(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Identify/upsert a user in Dittofeed.

    config/input_data:
      api_key — Dittofeed API key (required)
      user_id — User ID (required)
      traits  — User traits dict (optional)
    """
    merged = {**config, **input_data}
    user_id = merged.get("user_id", "")
    if not user_id:
        raise ValueError("user_id is required for ditofeed.identify_user")
    headers = _headers(config, input_data)
    payload = {"userId": user_id, "traits": merged.get("traits", {})}
    async with httpx.AsyncClient(base_url=DITOFEED_BASE, timeout=30) as client:
        r = await client.put("/users", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json() if r.text else {}
    log.info("ditofeed.identify_user", user_id=user_id)
    return {"result": data, "user_id": user_id}


@register_node("ditofeed.track_event")
async def track_event(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Track an event for a user in Dittofeed.

    config/input_data:
      api_key    — Dittofeed API key (required)
      user_id    — User ID (required)
      event_name — Name of the event (required)
      properties — Event properties dict (optional)
    """
    merged = {**config, **input_data}
    user_id = merged.get("user_id", "")
    event_name = merged.get("event_name", "") or merged.get("event", "")
    if not user_id or not event_name:
        raise ValueError("user_id and event_name are required for ditofeed.track_event")
    headers = _headers(config, input_data)
    payload = {
        "userId": user_id,
        "event": event_name,
        "properties": merged.get("properties", {}),
    }
    async with httpx.AsyncClient(base_url=DITOFEED_BASE, timeout=30) as client:
        r = await client.post("/events", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json() if r.text else {}
    log.info("ditofeed.track_event", user_id=user_id, event_name=event_name)
    return {"result": data, "user_id": user_id, "event_name": event_name}
