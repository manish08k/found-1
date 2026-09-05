"""Deepgram audio transcription integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

DEEPGRAM_BASE = "https://api.deepgram.com/v1"


@register_node("deepgram.transcribe_url")
async def deepgram_transcribe_url(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Transcribe audio from a URL using Deepgram.

    config/input_data:
      api_key   — Deepgram API key
      audio_url — publicly accessible URL of the audio file
      model     — model to use (default "nova-2")
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    audio_url = merged.get("audio_url") or ""
    model = merged.get("model") or "nova-2"

    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"url": audio_url}

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{DEEPGRAM_BASE}/listen",
            headers=headers,
            json=payload,
            params={"model": model},
        )
        r.raise_for_status()

    result = r.json()
    log.info("deepgram.transcribe_url", model=model)
    return {"result": result}


@register_node("deepgram.transcribe_file")
async def deepgram_transcribe_file(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Transcribe audio from a local file using Deepgram.

    config/input_data:
      api_key   — Deepgram API key
      file_path — local path to the audio file
      model     — model to use (default "nova-2")
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    file_path = merged.get("file_path") or ""
    model = merged.get("model") or "nova-2"

    with open(file_path, "rb") as f:
        audio_bytes = f.read()

    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "audio/*",
    }

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{DEEPGRAM_BASE}/listen",
            headers=headers,
            content=audio_bytes,
            params={"model": model},
        )
        r.raise_for_status()

    result = r.json()
    log.info("deepgram.transcribe_file", file_path=file_path, model=model)
    return {"result": result}


@register_node("deepgram.list_projects")
async def deepgram_list_projects(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List Deepgram projects.

    config/input_data:
      api_key — Deepgram API key
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""

    headers = {"Authorization": f"Token {api_key}"}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{DEEPGRAM_BASE}/projects", headers=headers)
        r.raise_for_status()

    result = r.json()
    log.info("deepgram.list_projects", count=len(result.get("projects", [])))
    return {"result": result}
