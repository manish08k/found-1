"""Camb AI speech translation and dubbing — handler for camb_ai integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.camb.ai/apis"


@register_node("camb_ai.create_tts")
async def camb_ai_create_tts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create text-to-speech.

    config/input_data:
      api_key — API key or token (required)
      text — (required)
      voice_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    text = merged.get("text") or ""
    voice_id = merged.get("voice_id") or ""
    if not text or not voice_id:
        raise ValueError("text, voice_id required for camb_ai.create_tts")
    payload = {"text": text, "voice_id": voice_id}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/tts", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("camb_ai.create_tts")
    return {"data": data}

@register_node("camb_ai.get_tts")
async def camb_ai_get_tts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get TTS result.

    config/input_data:
      api_key — API key or token (required)
      task_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    task_id = merged.get("task_id") or ""
    if not task_id:
        raise ValueError("task_id required for camb_ai.get_tts")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/tts/{task_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("camb_ai.get_tts")
    return {"data": data}

@register_node("camb_ai.list_voices")
async def camb_ai_list_voices(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List available voices.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/voices", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("camb_ai.list_voices")
    return {"data": data}
