"""Scenario integration — AI game asset generation."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.scenario.com/v1"


def _headers(config: dict) -> dict:
    import base64
    key_secret = f"{config.get('api_key', '')}:{config.get('secret', '')}".encode()
    encoded = base64.b64encode(key_secret).decode()
    return {"Authorization": f"Basic {encoded}", "Content-Type": "application/json"}


@register_node("scenario.generate_asset")
async def scenario_generate_asset(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    model_id = merged.get("model_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/models/{model_id}/inferences", json={
            "parameters": {
                "type": merged.get("type", "txt2img"),
                "prompt": merged.get("prompt", ""),
                "numSamples": merged.get("num_samples", 1),
            }
        })
        r.raise_for_status()
    return r.json()


@register_node("scenario.get_inference")
async def scenario_get_inference(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    model_id = merged.get("model_id", "")
    inference_id = merged.get("inference_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/models/{model_id}/inferences/{inference_id}")
        r.raise_for_status()
    return r.json()
