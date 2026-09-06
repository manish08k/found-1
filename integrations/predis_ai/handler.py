"""Predis AI integration — AI social media content creation."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://brain.predis.ai/predis_api/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("predis_ai.generate_post")
async def predis_ai_generate_post(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/create_post/", json={
            "brand_id": merged.get("brand_id", ""),
            "text": merged.get("text", ""),
            "media_type": merged.get("media_type", "single_image"),
        })
        r.raise_for_status()
    return r.json()
