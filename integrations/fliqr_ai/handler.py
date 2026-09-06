"""Fliqr AI integration — AI image generation and editing."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.fliqr.ai/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("fliqr_ai.generate_image")
async def fliqr_ai_generate_image(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/generate", json={
            "prompt": merged.get("prompt", ""),
            "style": merged.get("style", "realistic"),
            "width": merged.get("width", 512),
            "height": merged.get("height", 512),
        })
        r.raise_for_status()
    return r.json()
