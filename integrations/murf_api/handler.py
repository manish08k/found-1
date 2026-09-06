"""Murf API integration — AI voice generation."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.murf.ai/v1"


def _headers(config: dict) -> dict:
    return {"api-key": config.get("api_key", ""), "Content-Type": "application/json"}


@register_node("murf_api.generate_speech")
async def murf_api_generate_speech(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/speech/generate", json={
            "voiceId": merged.get("voice_id", "en-US-natalie"),
            "style": merged.get("style", "Conversational"),
            "text": merged.get("text", ""),
            "sampleRate": merged.get("sample_rate", 24000),
        })
        r.raise_for_status()
    data = r.json()
    return {"audio_file": data.get("audioFile"), "duration_millis": data.get("durationMillis")}


@register_node("murf_api.get_voices")
async def murf_api_get_voices(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/speech/voices")
        r.raise_for_status()
    return {"voices": r.json()}
