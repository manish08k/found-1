"""Image Router integration — AI image generation routing."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://ir-api.myqa.cc/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("image_router.generate_image")
async def image_router_generate_image(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/images/generations", json={
            "prompt": merged.get("prompt", ""),
            "model": merged.get("model", "stable-diffusion-xl"),
            "n": merged.get("n", 1),
            "size": merged.get("size", "1024x1024"),
        })
        r.raise_for_status()
    return r.json()
