"""AssemblyAI speech-to-text integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

ASSEMBLYAI_BASE = "https://api.assemblyai.com/v2"


@register_node("assemblyai.transcribe")
async def assemblyai_transcribe(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Submit an audio file URL for transcription.

    config/input_data:
      api_key   — AssemblyAI API key
      audio_url — publicly accessible URL of the audio file
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    audio_url = merged.get("audio_url") or ""

    headers = {"Authorization": api_key, "Content-Type": "application/json"}
    payload = {"audio_url": audio_url}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{ASSEMBLYAI_BASE}/transcript", headers=headers, json=payload)
        r.raise_for_status()

    result = r.json()
    log.info("assemblyai.transcribe", transcript_id=result.get("id"), status=result.get("status"))
    return {"result": result}


@register_node("assemblyai.get_transcript")
async def assemblyai_get_transcript(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a transcript by ID.

    config/input_data:
      api_key       — AssemblyAI API key
      transcript_id — ID of the transcript to retrieve
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    transcript_id = merged.get("transcript_id") or ""

    headers = {"Authorization": api_key}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{ASSEMBLYAI_BASE}/transcript/{transcript_id}", headers=headers)
        r.raise_for_status()

    result = r.json()
    log.info("assemblyai.get_transcript", transcript_id=transcript_id, status=result.get("status"))
    return {"result": result}


@register_node("assemblyai.list_transcripts")
async def assemblyai_list_transcripts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List recent transcripts.

    config/input_data:
      api_key — AssemblyAI API key
      limit   — number of transcripts to return (default 20)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    limit = int(merged.get("limit", 20))

    headers = {"Authorization": api_key}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{ASSEMBLYAI_BASE}/transcript", headers=headers, params={"limit": limit})
        r.raise_for_status()

    result = r.json()
    log.info("assemblyai.list_transcripts", count=len(result.get("transcripts", [])))
    return {"result": result}
