"""
Speech-to-text nodes.

Nodes:
  speechtotext.assemblyai.transcribe  — AssemblyAI async transcription
  speechtotext.assemblyai.realtime    — AssemblyAI real-time (submit audio URL)
  speechtotext.openai_whisper         — OpenAI Whisper via file upload
"""
import asyncio
import time

import httpx
import structlog

from core.config import settings
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


# ─── speechtotext.assemblyai.transcribe ──────────────────────────────────────

@register_node("speechtotext.assemblyai.transcribe")
async def stt_assemblyai_transcribe(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Submit an audio file URL to AssemblyAI and poll until transcription completes.
    config: api_key, language_code, speaker_labels, auto_chapters, sentiment_analysis,
            entity_detection, punctuate, format_text, poll_interval_seconds, timeout_seconds
    input_data: audio_url (public URL) OR audio_base64 (base64-encoded audio bytes)
    """
    api_key = config.get("api_key") or getattr(settings, "ASSEMBLYAI_API_KEY", "")
    if not api_key:
        raise ValueError("speechtotext.assemblyai requires ASSEMBLYAI_API_KEY")

    audio_url = input_data.get("audio_url") or config.get("audio_url", "")
    audio_b64 = input_data.get("audio_base64", "")
    poll_interval = float(config.get("poll_interval_seconds", 3.0))
    timeout = float(config.get("timeout_seconds", 300.0))

    headers = {"Authorization": api_key, "Content-Type": "application/json"}
    base_url = "https://api.assemblyai.com/v2"

    async with httpx.AsyncClient(timeout=30) as c:
        # If base64 audio provided, upload it first
        if audio_b64 and not audio_url:
            import base64
            audio_bytes = base64.b64decode(audio_b64)
            upload_r = await c.post(f"{base_url}/upload",
                                    headers={**headers, "Content-Type": "application/octet-stream"},
                                    content=audio_bytes)
            upload_r.raise_for_status()
            audio_url = upload_r.json()["upload_url"]

        if not audio_url:
            return {"error": "audio_url or audio_base64 required", "transcript": None}

        # Submit transcription
        payload: dict = {"audio_url": audio_url}
        optional_flags = [
            "language_code", "speaker_labels", "auto_chapters", "sentiment_analysis",
            "entity_detection", "punctuate", "format_text", "auto_highlights",
            "content_safety", "iab_categories", "custom_spelling",
        ]
        for flag in optional_flags:
            if flag in config:
                payload[flag] = config[flag]

        submit_r = await c.post(f"{base_url}/transcript", headers=headers, json=payload)
        submit_r.raise_for_status()
        transcript_id = submit_r.json()["id"]

    # Poll for completion
    start = time.time()
    while time.time() - start < timeout:
        await asyncio.sleep(poll_interval)
        async with httpx.AsyncClient(timeout=15) as c:
            poll_r = await c.get(f"{base_url}/transcript/{transcript_id}", headers=headers)
            poll_r.raise_for_status()
            data = poll_r.json()

        status = data.get("status")
        if status == "completed":
            return {
                "transcript": data.get("text", ""),
                "transcript_id": transcript_id,
                "status": "completed",
                "words": data.get("words", []),
                "utterances": data.get("utterances", []),
                "chapters": data.get("chapters", []),
                "sentiment_analysis_results": data.get("sentiment_analysis_results", []),
                "entities": data.get("entities", []),
                "confidence": data.get("confidence"),
                "audio_duration": data.get("audio_duration"),
            }
        if status == "error":
            return {"error": data.get("error", "Unknown error"), "transcript_id": transcript_id, "status": "error"}
        # Still processing
        log.debug("assemblyai_polling", transcript_id=transcript_id, status=status)

    return {"error": "Transcription timed out", "transcript_id": transcript_id, "status": "timeout"}


# ─── speechtotext.assemblyai.realtime ────────────────────────────────────────

@register_node("speechtotext.assemblyai.realtime")
async def stt_assemblyai_realtime(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Submit an audio URL for transcription with real-time options.
    This is a convenience wrapper around transcribe with short audio files
    and reduced polling.
    """
    config_copy = dict(config)
    config_copy["poll_interval_seconds"] = config.get("poll_interval_seconds", 1.0)
    config_copy["timeout_seconds"] = config.get("timeout_seconds", 60.0)
    return await stt_assemblyai_transcribe(config_copy, input_data, credential_id, db)


# ─── speechtotext.openai_whisper ─────────────────────────────────────────────

@register_node("speechtotext.openai_whisper")
async def stt_openai_whisper(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Transcribe audio using OpenAI Whisper API.
    config: model (whisper-1), language, response_format, temperature
    input_data: audio_url (fetched and uploaded) OR audio_base64
    """
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise ValueError("speechtotext.openai_whisper requires OPENAI_API_KEY")

    model = config.get("model", "whisper-1")
    language = config.get("language", "")
    response_format = config.get("response_format", "json")
    temperature = float(config.get("temperature", 0.0))

    audio_b64 = input_data.get("audio_base64", "")
    audio_url = input_data.get("audio_url", "")
    audio_bytes = b""
    filename = "audio.mp3"

    if audio_b64:
        import base64
        audio_bytes = base64.b64decode(audio_b64)
        filename = input_data.get("filename", "audio.mp3")
    elif audio_url:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.get(audio_url)
            r.raise_for_status()
            audio_bytes = r.content
            filename = audio_url.split("/")[-1].split("?")[0] or "audio.mp3"

    if not audio_bytes:
        return {"error": "audio_url or audio_base64 required", "transcript": None}

    import io
    files = {"file": (filename, io.BytesIO(audio_bytes), "audio/mpeg")}
    data: dict = {"model": model, "response_format": response_format}
    if language:
        data["language"] = language
    if temperature > 0:
        data["temperature"] = str(temperature)

    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            data=data,
            files=files,
        )
        r.raise_for_status()
        result = r.json() if response_format == "json" else {"text": r.text}

    return {
        "transcript": result.get("text", r.text if response_format != "json" else ""),
        "model": model,
        "language": language or "auto-detected",
    }
