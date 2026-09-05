"""HeyGen AI video generation integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

HEYGEN_BASE = "https://api.heygen.com/v2"


@register_node("heygen.create_video")
async def heygen_create_video(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create an AI avatar video using HeyGen.

    config/input_data:
      api_key   — HeyGen API key
      avatar_id — ID of the avatar to use
      voice_id  — ID of the voice to use
      script    — text script for the avatar to speak
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    avatar_id = merged.get("avatar_id") or ""
    voice_id = merged.get("voice_id") or ""
    script = merged.get("script") or ""

    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    payload = {
        "video_inputs": [
            {
                "character": {"type": "avatar", "avatar_id": avatar_id},
                "voice": {"type": "text", "input_text": script, "voice_id": voice_id},
            }
        ],
        "dimension": {"width": 1280, "height": 720},
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{HEYGEN_BASE}/video/generate", headers=headers, json=payload)
        r.raise_for_status()

    result = r.json()
    log.info("heygen.create_video", video_id=result.get("data", {}).get("video_id"))
    return {"result": result}


@register_node("heygen.get_video")
async def heygen_get_video(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get the status and details of a HeyGen video.

    config/input_data:
      api_key  — HeyGen API key
      video_id — ID of the video to retrieve
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    video_id = merged.get("video_id") or ""

    headers = {"X-Api-Key": api_key}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{HEYGEN_BASE}/video/{video_id}", headers=headers)
        r.raise_for_status()

    result = r.json()
    log.info("heygen.get_video", video_id=video_id, status=result.get("data", {}).get("status"))
    return {"result": result}


@register_node("heygen.list_avatars")
async def heygen_list_avatars(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List available HeyGen avatars.

    config/input_data:
      api_key — HeyGen API key
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""

    headers = {"X-Api-Key": api_key}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{HEYGEN_BASE}/avatars", headers=headers)
        r.raise_for_status()

    result = r.json()
    log.info("heygen.list_avatars", count=len(result.get("data", {}).get("avatars", [])))
    return {"result": result}


@register_node("heygen.list_voices")
async def heygen_list_voices(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List available HeyGen voices.

    config/input_data:
      api_key — HeyGen API key
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""

    headers = {"X-Api-Key": api_key}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{HEYGEN_BASE}/voices", headers=headers)
        r.raise_for_status()

    result = r.json()
    log.info("heygen.list_voices", count=len(result.get("data", {}).get("voices", [])))
    return {"result": result}
