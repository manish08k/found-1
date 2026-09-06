"""Hume AI integration — empathic AI and voice expression."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.hume.ai/v0"


def _headers(config: dict) -> dict:
    return {"X-Hume-Api-Key": config.get("api_key", ""), "Content-Type": "application/json"}


@register_node("hume_ai.analyze_expression")
async def hume_ai_analyze_expression(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/batch/jobs", json={
            "urls": [merged.get("url", "")],
            "models": {"face": {}, "prosody": {}},
        })
        r.raise_for_status()
    return r.json()


@register_node("hume_ai.get_job_predictions")
async def hume_ai_get_job_predictions(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    job_id = merged.get("job_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/batch/jobs/{job_id}/predictions")
        r.raise_for_status()
    return r.json()
