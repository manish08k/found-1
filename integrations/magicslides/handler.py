"""MagicSlides integration — AI presentation generation."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.magicslides.app/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("magicslides.generate_presentation")
async def magicslides_generate_presentation(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/generate", json={
            "topic": merged.get("topic", ""),
            "num_slides": merged.get("num_slides", 10),
            "template": merged.get("template", "default"),
        })
        r.raise_for_status()
    return r.json()
