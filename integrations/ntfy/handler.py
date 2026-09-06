"""ntfy push notification service — handler for ntfy integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://ntfy.sh"


@register_node("ntfy.publish")
async def ntfy_publish(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Publish a notification.

    config/input_data:
      topic — (required)
      message — (required)
    """
    merged = {**config, **input_data}
    headers = {"Content-Type": "application/json"}
    topic = merged.get("topic") or ""
    message = merged.get("message") or ""
    if not topic or not message:
        raise ValueError("topic, message required for ntfy.publish")
    payload = {"message": message}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/{topic}", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("ntfy.publish")
    return {"data": data}
