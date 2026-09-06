"""Gladia integration — real-time audio transcription."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.gladia.io/v2"


def _headers(config: dict) -> dict:
    return {"x-gladia-key": config.get("api_key", ""), "Content-Type": "application/json"}


@register_node("gladia.transcribe_audio")
async def gladia_transcribe_audio(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/pre-recorded", json={
            "audio_url": merged.get("audio_url", ""),
            "language": merged.get("language"),
            "diarization": merged.get("diarization", False),
        })
        r.raise_for_status()
    return r.json()


@register_node("gladia.get_transcription")
async def gladia_get_transcription(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    transcription_id = merged.get("transcription_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/pre-recorded/{transcription_id}")
        r.raise_for_status()
    return r.json()
