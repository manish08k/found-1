"""Robolly integration — dynamic image generation for marketing."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://app.robolly.com/api"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("robolly.generate_image")
async def robolly_generate_image(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    template_id = merged.get("template_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.get(f"{BASE}/template/{template_id}/render.jpg", params=merged.get("modifications", {}))
        r.raise_for_status()
    import base64
    return {"image_base64": base64.b64encode(r.content).decode(), "content_type": "image/jpeg"}


@register_node("robolly.get_templates")
async def robolly_get_templates(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/templates")
        r.raise_for_status()
    return {"templates": r.json()}
