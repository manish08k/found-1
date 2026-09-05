"""ManyChat integration — chatbot platform via ManyChat API."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

MANYCHAT_BASE = "https://api.manychat.com/fb"


def _headers(config: dict, input_data: dict) -> dict:
    merged = {**config, **input_data}
    return {"Authorization": f"Bearer {merged.get('api_key', '')}"}


@register_node("manychat.list_custom_fields")
async def list_custom_fields(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all custom fields for the ManyChat page.

    config/input_data:
      api_key — ManyChat API key (required)
    """
    headers = _headers(config, input_data)
    async with httpx.AsyncClient(base_url=MANYCHAT_BASE, timeout=30) as client:
        r = await client.get("/page/getCustomFields", headers=headers)
        r.raise_for_status()
        data = r.json()
    fields = data.get("data", [])
    log.info("manychat.list_custom_fields", count=len(fields))
    return {"custom_fields": fields, "count": len(fields)}


@register_node("manychat.get_subscriber")
async def get_subscriber(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get subscriber info by subscriber ID.

    config/input_data:
      api_key       — ManyChat API key (required)
      subscriber_id — Subscriber ID (required)
    """
    merged = {**config, **input_data}
    subscriber_id = merged.get("subscriber_id", "")
    if not subscriber_id:
        raise ValueError("subscriber_id is required for manychat.get_subscriber")
    headers = _headers(config, input_data)
    async with httpx.AsyncClient(base_url=MANYCHAT_BASE, timeout=30) as client:
        r = await client.get(
            "/subscriber/getInfo",
            params={"subscriber_id": subscriber_id},
            headers=headers,
        )
        r.raise_for_status()
        data = r.json()
    log.info("manychat.get_subscriber", subscriber_id=subscriber_id)
    return {"subscriber": data.get("data", data), "subscriber_id": subscriber_id}


@register_node("manychat.set_custom_field")
async def set_custom_field(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Set a custom field value for a subscriber.

    config/input_data:
      api_key       — ManyChat API key (required)
      subscriber_id — Subscriber ID (required)
      field_id      — Custom field ID (required)
      field_value   — Value to set (required)
    """
    merged = {**config, **input_data}
    subscriber_id = merged.get("subscriber_id", "")
    field_id = merged.get("field_id", "")
    field_value = merged.get("field_value", "")
    if not subscriber_id or not field_id:
        raise ValueError("subscriber_id and field_id are required for manychat.set_custom_field")
    headers = _headers(config, input_data)
    payload = {"subscriber_id": subscriber_id, "field_id": field_id, "field_value": field_value}
    async with httpx.AsyncClient(base_url=MANYCHAT_BASE, timeout=30) as client:
        r = await client.post("/subscriber/setCustomField", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("manychat.set_custom_field", subscriber_id=subscriber_id, field_id=field_id)
    return {"result": data, "subscriber_id": subscriber_id, "field_id": field_id}


@register_node("manychat.send_content")
async def send_content(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send content to a subscriber via ManyChat.

    config/input_data:
      api_key       — ManyChat API key (required)
      subscriber_id — Subscriber ID (required)
      data          — Content data dict (required)
    """
    merged = {**config, **input_data}
    subscriber_id = merged.get("subscriber_id", "")
    content_data = merged.get("data", {})
    if not subscriber_id:
        raise ValueError("subscriber_id is required for manychat.send_content")
    headers = _headers(config, input_data)
    payload = {"subscriber_id": subscriber_id, "data": content_data}
    async with httpx.AsyncClient(base_url=MANYCHAT_BASE, timeout=30) as client:
        r = await client.post("/sending/sendContent", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("manychat.send_content", subscriber_id=subscriber_id)
    return {"result": data, "subscriber_id": subscriber_id}
