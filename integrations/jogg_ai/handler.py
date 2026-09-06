"""Jogg AI integration — AI video generation from text."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.jogg.ai/v1"


def _headers(config: dict) -> dict:
    return {"x-api-key": config.get("api_key", ""), "Content-Type": "application/json"}


@register_node("jogg_ai.create_video")
async def jogg_ai_create_video(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/create", json={
            "script": merged.get("script", ""),
            "avatar_id": merged.get("avatar_id", ""),
            "voice_id": merged.get("voice_id", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("jogg_ai.get_video_status")
async def jogg_ai_get_video_status(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    video_id = merged.get("video_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/videos/{video_id}")
        r.raise_for_status()
    return r.json()
