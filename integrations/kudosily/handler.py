"""Kudosily — employee recognition integration."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

KUDOSILY_BASE = "https://api.kudosily.com/api/v1"


def _headers(config: dict) -> dict:
    api_key = config.get("api_key", "")
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


@register_node("kudosily.list_recognitions")
async def kudosily_list_recognitions(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List employee recognitions from Kudosily.

    config:
      api_key — Kudosily API key
      limit   — number of recognitions to return (default 25)
    """
    limit = int(config.get("limit", 25))

    async with httpx.AsyncClient(base_url=KUDOSILY_BASE, timeout=30) as client:
        r = await client.get("/recognitions", params={"limit": limit}, headers=_headers(config))
        r.raise_for_status()
        data = r.json()

    recognitions = data.get("data", data if isinstance(data, list) else [])
    log.info("kudosily.list_recognitions", count=len(recognitions))
    return {"recognitions": recognitions, "count": len(recognitions)}


@register_node("kudosily.create_recognition")
async def kudosily_create_recognition(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create an employee recognition in Kudosily.

    config/input_data:
      api_key      — Kudosily API key
      recipient_id — recipient user ID (required)
      message      — recognition message text (required)
      value_id     — company value ID to associate (optional)
    """
    recipient_id = config.get("recipient_id") or input_data.get("recipient_id")
    message = config.get("message") or input_data.get("message")
    value_id = config.get("value_id") or input_data.get("value_id")

    if not recipient_id:
        raise ValueError("recipient_id is required for kudosily.create_recognition")
    if not message:
        raise ValueError("message is required for kudosily.create_recognition")

    payload: dict = {"recipient_id": recipient_id, "message": message}
    if value_id:
        payload["value"] = value_id

    async with httpx.AsyncClient(base_url=KUDOSILY_BASE, timeout=30) as client:
        r = await client.post("/recognitions", json=payload, headers=_headers(config))
        r.raise_for_status()
        recognition = r.json()

    log.info("kudosily.create_recognition", recipient_id=recipient_id)
    return {"recognition": recognition, "id": recognition.get("id"), "recipient_id": recipient_id}
