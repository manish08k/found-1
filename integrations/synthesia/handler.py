"""Synthesia AI video generation integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

SYNTHESIA_BASE = "https://api.synthesia.io/v2"


@register_node("synthesia.create_video")
async def synthesia_create_video(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create an AI video using Synthesia.

    config/input_data:
      api_key   — Synthesia API key
      title     — video title
      desc      — video description
      script    — text script for the presenter
      avatar_id — ID of the avatar to use
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    title = merged.get("title") or "Untitled Video"
    desc = merged.get("desc") or ""
    script = merged.get("script") or ""
    avatar_id = merged.get("avatar_id") or ""

    headers = {"Authorization": api_key, "Content-Type": "application/json"}
    payload = {
        "test": True,
        "title": title,
        "description": desc,
        "visibility": "private",
        "input": [{"scriptText": script, "avatar": avatar_id}],
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{SYNTHESIA_BASE}/videos", headers=headers, json=payload)
        r.raise_for_status()

    result = r.json()
    log.info("synthesia.create_video", video_id=result.get("id"))
    return {"result": result}


@register_node("synthesia.get_video")
async def synthesia_get_video(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get the status and details of a Synthesia video.

    config/input_data:
      api_key  — Synthesia API key
      video_id — ID of the video to retrieve
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    video_id = merged.get("video_id") or ""

    headers = {"Authorization": api_key}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{SYNTHESIA_BASE}/videos/{video_id}", headers=headers)
        r.raise_for_status()

    result = r.json()
    log.info("synthesia.get_video", video_id=video_id, status=result.get("status"))
    return {"result": result}


@register_node("synthesia.list_videos")
async def synthesia_list_videos(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Synthesia videos.

    config/input_data:
      api_key — Synthesia API key
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""

    headers = {"Authorization": api_key}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{SYNTHESIA_BASE}/videos", headers=headers)
        r.raise_for_status()

    result = r.json()
    log.info("synthesia.list_videos", count=len(result.get("videos", [])))
    return {"result": result}
