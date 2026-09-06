"""Supadata integration — YouTube data extraction."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.supadata.ai/v1"


def _headers(config: dict) -> dict:
    return {"x-api-key": config.get("api_key", ""), "Content-Type": "application/json"}


@register_node("supadata.get_transcript")
async def supadata_get_transcript(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/youtube/transcript", params={"url": merged.get("url", ""), "lang": merged.get("language", "en")})
        r.raise_for_status()
    return r.json()


@register_node("supadata.get_video_info")
async def supadata_get_video_info(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/youtube/video", params={"url": merged.get("url", "")})
        r.raise_for_status()
    return r.json()
