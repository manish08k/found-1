"""Ntly integration — notifications via Ntly API v1."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

NTLY_BASE = "https://app.ntly.io/api/v1"


def _headers(config: dict, input_data: dict) -> dict:
    merged = {**config, **input_data}
    return {"Authorization": f"Bearer {merged.get('api_key', '')}"}


@register_node("ntly.send_notification")
async def send_notification(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a notification via Ntly.

    config/input_data:
      api_key — Ntly API key (required)
      title   — Notification title (required)
      message — Notification message (required)
    """
    merged = {**config, **input_data}
    title = merged.get("title", "")
    message = merged.get("message", "")
    if not title or not message:
        raise ValueError("title and message are required for ntly.send_notification")
    headers = _headers(config, input_data)
    payload = {"title": title, "message": message}
    async with httpx.AsyncClient(base_url=NTLY_BASE, timeout=30) as client:
        r = await client.post("/notifications", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("ntly.send_notification", title=title)
    return {"result": data, "title": title}


@register_node("ntly.list_notifications")
async def list_notifications(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List notifications from Ntly.

    config/input_data:
      api_key — Ntly API key (required)
    """
    headers = _headers(config, input_data)
    async with httpx.AsyncClient(base_url=NTLY_BASE, timeout=30) as client:
        r = await client.get("/notifications", headers=headers)
        r.raise_for_status()
        data = r.json()
    notifications = data.get("notifications", data) if isinstance(data, dict) else data
    log.info("ntly.list_notifications")
    return {"notifications": notifications}
