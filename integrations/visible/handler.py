"""Visible investor reporting and metrics — handler for visible integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.visible.vc/v2"


@register_node("visible.list_metrics")
async def visible_list_metrics(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List metrics.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/metrics", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("visible.list_metrics")
    return {"data": data}

@register_node("visible.create_update")
async def visible_create_update(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create an investor update.

    config/input_data:
      api_key — API key or token (required)
      subject — (required)
      body — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    subject = merged.get("subject") or ""
    body = merged.get("body") or ""
    if not subject or not body:
        raise ValueError("subject, body required for visible.create_update")
    payload = {"subject": subject, "body": body}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/updates", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("visible.create_update")
    return {"data": data}

@register_node("visible.list_updates")
async def visible_list_updates(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List updates.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/updates", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("visible.list_updates")
    return {"data": data}
