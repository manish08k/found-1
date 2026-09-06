"""Gistly integration — AI YouTube video summarization."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://gistly.net/api/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("gistly.summarize_video")
async def gistly_summarize_video(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/summarize", json={
            "video_url": merged.get("video_url", ""),
            "language": merged.get("language", "en"),
        })
        r.raise_for_status()
    return r.json()
