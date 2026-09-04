"""
ElevenLabs API integration.

Credential fields:
  - api_key: ElevenLabs API key (xi-api-key header)

Auth: xi-api-key header
Base URL: https://api.elevenlabs.io/v1
"""
import base64
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("ElevenLabs credential is missing 'api_key'")
    return httpx.AsyncClient(
        base_url=ELEVENLABS_BASE_URL,
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
        },
        timeout=120.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"ElevenLabs API error {r.status_code}: {detail}")
    try:
        return r.json()
    except Exception:
        return {"raw": r.text}


def _check_binary(r: httpx.Response) -> dict:
    """Check response and return binary audio as base64."""
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"ElevenLabs API error {r.status_code}: {detail}")
    audio_b64 = base64.b64encode(r.content).decode()
    content_type = r.headers.get("content-type", "audio/mpeg")
    return {"audio_base64": audio_b64, "content_type": content_type}


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@register_node("elevenlabs.text_to_speech")
async def elevenlabs_text_to_speech(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /text-to-speech/{voice_id} — convert text to speech. Returns base64-encoded audio."""
    voice_id = config.get("voice_id") or input_data.get("voice_id", "21m00Tcm4TlvDq8ikWAM")
    text = config.get("text") or input_data.get("text")
    if not text:
        raise ValueError("elevenlabs.text_to_speech requires 'text'")
    body: dict = {
        "text": text,
        "model_id": config.get("model_id") or input_data.get("model_id", "eleven_monolingual_v1"),
    }
    voice_settings = config.get("voice_settings") or input_data.get("voice_settings")
    if voice_settings:
        body["voice_settings"] = voice_settings
    else:
        stability = config.get("stability") or input_data.get("stability")
        similarity_boost = config.get("similarity_boost") or input_data.get("similarity_boost")
        if stability is not None or similarity_boost is not None:
            body["voice_settings"] = {
                "stability": float(stability) if stability is not None else 0.5,
                "similarity_boost": float(similarity_boost) if similarity_boost is not None else 0.75,
            }
    output_format = config.get("output_format") or input_data.get("output_format", "mp3_44100_128")
    async with await _client(credential_id, db) as client:
        r = await client.post(
            f"/text-to-speech/{voice_id}",
            json=body,
            params={"output_format": output_format},
            headers={"Accept": "audio/mpeg"},
        )
    return _check_binary(r)


@register_node("elevenlabs.list_voices")
async def elevenlabs_list_voices(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /voices — list all available voices."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/voices")
    return _check(r)


@register_node("elevenlabs.get_voice")
async def elevenlabs_get_voice(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /voices/{voice_id} — get details of a specific voice."""
    voice_id = config.get("voice_id") or input_data.get("voice_id")
    if not voice_id:
        raise ValueError("elevenlabs.get_voice requires 'voice_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/voices/{voice_id}")
    return _check(r)


@register_node("elevenlabs.add_voice")
async def elevenlabs_add_voice(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /voices/add — add a cloned voice from audio files."""
    name = config.get("name") or input_data.get("name")
    files = config.get("files") or input_data.get("files")  # list of base64-encoded audio files
    if not name:
        raise ValueError("elevenlabs.add_voice requires 'name'")
    if not files:
        raise ValueError("elevenlabs.add_voice requires 'files' (list of base64-encoded audio)")
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    multipart_files = []
    for i, f in enumerate(files):
        if isinstance(f, str):
            file_bytes = base64.b64decode(f)
        else:
            file_bytes = f
        multipart_files.append(("files", (f"audio_{i}.mp3", file_bytes, "audio/mpeg")))
    description = config.get("description") or input_data.get("description", "")
    async with httpx.AsyncClient(
        base_url=ELEVENLABS_BASE_URL,
        headers={"xi-api-key": api_key},
        timeout=120.0,
    ) as client:
        r = await client.post(
            "/voices/add",
            data={"name": name, "description": description},
            files=multipart_files,
        )
    return _check(r)


@register_node("elevenlabs.edit_voice")
async def elevenlabs_edit_voice(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /voices/{voice_id}/edit — edit a voice's metadata."""
    voice_id = config.get("voice_id") or input_data.get("voice_id")
    if not voice_id:
        raise ValueError("elevenlabs.edit_voice requires 'voice_id'")
    body: dict = {}
    for field in ("name", "description"):
        v = config.get(field) or input_data.get(field)
        if v:
            body[field] = v
    labels = config.get("labels") or input_data.get("labels")
    if labels:
        body["labels"] = labels
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/voices/{voice_id}/edit", json=body)
    return _check(r)


@register_node("elevenlabs.delete_voice")
async def elevenlabs_delete_voice(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /voices/{voice_id} — delete a voice."""
    voice_id = config.get("voice_id") or input_data.get("voice_id")
    if not voice_id:
        raise ValueError("elevenlabs.delete_voice requires 'voice_id'")
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/voices/{voice_id}")
    return _check(r)


@register_node("elevenlabs.get_user")
async def elevenlabs_get_user(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /user — get current user information and subscription details."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/user")
    return _check(r)


@register_node("elevenlabs.list_models")
async def elevenlabs_list_models(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /models — list all available TTS models."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/models")
    return _check(r)


@register_node("elevenlabs.create_voice_sample")
async def elevenlabs_create_voice_sample(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /text-to-speech/{voice_id}/stream — create a voice sample via streaming (returned as base64)."""
    voice_id = config.get("voice_id") or input_data.get("voice_id", "21m00Tcm4TlvDq8ikWAM")
    text = config.get("text") or input_data.get("text")
    if not text:
        raise ValueError("elevenlabs.create_voice_sample requires 'text'")
    body: dict = {
        "text": text,
        "model_id": config.get("model_id") or input_data.get("model_id", "eleven_monolingual_v1"),
    }
    chunks = []
    async with await _client(credential_id, db) as client:
        async with client.stream("POST", f"/text-to-speech/{voice_id}/stream", json=body) as r:
            if not r.is_success:
                raise ValueError(f"ElevenLabs API error {r.status_code}")
            async for chunk in r.aiter_bytes():
                chunks.append(chunk)
    audio_b64 = base64.b64encode(b"".join(chunks)).decode()
    return {"audio_base64": audio_b64, "content_type": "audio/mpeg"}


@register_node("elevenlabs.speech_to_speech")
async def elevenlabs_speech_to_speech(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /speech-to-speech/{voice_id} — transform audio using a target voice."""
    voice_id = config.get("voice_id") or input_data.get("voice_id")
    audio_data = config.get("audio") or input_data.get("audio")  # base64-encoded audio
    if not voice_id:
        raise ValueError("elevenlabs.speech_to_speech requires 'voice_id'")
    if not audio_data:
        raise ValueError("elevenlabs.speech_to_speech requires 'audio' (base64-encoded)")
    if isinstance(audio_data, str):
        audio_bytes = base64.b64decode(audio_data)
    else:
        audio_bytes = audio_data
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    model_id = config.get("model_id") or input_data.get("model_id", "eleven_english_sts_v2")
    async with httpx.AsyncClient(
        base_url=ELEVENLABS_BASE_URL,
        headers={"xi-api-key": api_key},
        timeout=120.0,
    ) as client:
        r = await client.post(
            f"/speech-to-speech/{voice_id}",
            data={"model_id": model_id},
            files={"audio": ("input.mp3", audio_bytes, "audio/mpeg")},
        )
    return _check_binary(r)


async def test_connection(credential_id: str, db) -> dict:
    """Test ElevenLabs connection by fetching user information."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/user")
    _check(r)
    return {"ok": True}
