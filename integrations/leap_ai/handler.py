"""Leap AI integration — AI image generation and training."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.tryleap.ai/api/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("leap_ai.generate_image")
async def leap_ai_generate_image(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    model_id = merged.get("model_id", "26a1a203-3a46-42cb-8cfa-f4de075907d8")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/images/models/{model_id}/inferences", json={
            "prompt": merged.get("prompt", ""),
            "negative_prompt": merged.get("negative_prompt", ""),
            "steps": merged.get("steps", 50),
            "width": merged.get("width", 512),
            "height": merged.get("height", 512),
        })
        r.raise_for_status()
    return r.json()


@register_node("leap_ai.get_inference")
async def leap_ai_get_inference(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    model_id = merged.get("model_id", "")
    inference_id = merged.get("inference_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/images/models/{model_id}/inferences/{inference_id}")
        r.raise_for_status()
    return r.json()
