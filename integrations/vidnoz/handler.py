"""Vidnoz integration — AI avatar video creation and management."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

VIDNOZ_BASE = "https://api.vidnoz.com/v1"


def _vidnoz_headers(api_key: str) -> dict:
    return {"x-api-key": api_key, "Content-Type": "application/json"}


@register_node("vidnoz.list_templates")
async def vidnoz_list_templates(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List available video templates in Vidnoz.

    config:
      api_key  — Vidnoz API key (required)
      page     — page number (optional, default 1)
      per_page — results per page (optional, default 20)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for vidnoz.list_templates")

    params: dict = {"page": merged.get("page", 1), "per_page": merged.get("per_page", 20)}

    async with httpx.AsyncClient(base_url=VIDNOZ_BASE, timeout=30) as client:
        r = await client.get("/templates", headers=_vidnoz_headers(api_key), params=params)
        r.raise_for_status()
        data = r.json()

    templates = data.get("data", data) if isinstance(data, dict) else data
    log.info("vidnoz.list_templates", count=len(templates) if isinstance(templates, list) else 1)
    return {"templates": templates, "count": len(templates) if isinstance(templates, list) else None}


@register_node("vidnoz.create_video")
async def vidnoz_create_video(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create an AI avatar video with Vidnoz.

    config:
      api_key     — Vidnoz API key (required)
      template_id — template ID to use (optional)
      avatar_id   — avatar ID (optional)
      voice_id    — voice ID for narration (optional)
      script      — video script text (required if no template)
      title       — video title (optional)
      webhook_url — URL to receive completion notification (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for vidnoz.create_video")

    payload: dict = {}
    for field in ["template_id", "avatar_id", "voice_id", "script", "title", "webhook_url"]:
        if merged.get(field):
            payload[field] = merged[field]

    async with httpx.AsyncClient(base_url=VIDNOZ_BASE, timeout=60) as client:
        r = await client.post("/videos", headers=_vidnoz_headers(api_key), json=payload)
        r.raise_for_status()
        video = r.json()

    video_id = video.get("id") or video.get("video_id")
    log.info("vidnoz.create_video", video_id=video_id, status=video.get("status"))
    return {"video": video, "video_id": video_id, "status": video.get("status")}


@register_node("vidnoz.get_video")
async def vidnoz_get_video(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get the status and details of a Vidnoz video.

    config:
      api_key  — Vidnoz API key (required)
      video_id — video ID to retrieve (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    video_id = merged.get("video_id")
    if not api_key or not video_id:
        raise ValueError("api_key and video_id are required for vidnoz.get_video")

    async with httpx.AsyncClient(base_url=VIDNOZ_BASE, timeout=30) as client:
        r = await client.get(f"/videos/{video_id}", headers=_vidnoz_headers(api_key))
        r.raise_for_status()
        video = r.json()

    log.info("vidnoz.get_video", video_id=video_id, status=video.get("status"))
    return {"video": video, "video_id": video_id, "status": video.get("status")}


@register_node("vidnoz.list_videos")
async def vidnoz_list_videos(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all videos in your Vidnoz account.

    config:
      api_key  — Vidnoz API key (required)
      page     — page number (optional, default 1)
      per_page — results per page (optional, default 20)
      status   — filter by status (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for vidnoz.list_videos")

    params: dict = {"page": merged.get("page", 1), "per_page": merged.get("per_page", 20)}
    if merged.get("status"):
        params["status"] = merged["status"]

    async with httpx.AsyncClient(base_url=VIDNOZ_BASE, timeout=30) as client:
        r = await client.get("/videos", headers=_vidnoz_headers(api_key), params=params)
        r.raise_for_status()
        data = r.json()

    videos = data.get("data", data) if isinstance(data, dict) else data
    log.info("vidnoz.list_videos", count=len(videos) if isinstance(videos, list) else 1)
    return {"videos": videos, "count": len(videos) if isinstance(videos, list) else None}
