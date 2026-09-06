"""VidLab7 integration — AI video creation and management."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

VIDLAB7_BASE = "https://api.vidlab7.com/v1"


def _vidlab7_headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


@register_node("vidlab7.create_video")
async def vidlab7_create_video(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new video using VidLab7.

    config:
      api_key     — VidLab7 API key (required)
      template_id — template ID to use for generation (optional)
      title       — video title (optional)
      script      — video script/narration text (optional)
      variables   — dict of template variable values (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for vidlab7.create_video")

    payload: dict = {}
    for field in ["template_id", "title", "script", "variables"]:
        if merged.get(field):
            payload[field] = merged[field]

    async with httpx.AsyncClient(base_url=VIDLAB7_BASE, timeout=60) as client:
        r = await client.post("/videos", headers=_vidlab7_headers(api_key), json=payload)
        r.raise_for_status()
        video = r.json()

    video_id = video.get("id")
    log.info("vidlab7.create_video", video_id=video_id, status=video.get("status"))
    return {"video": video, "video_id": video_id, "status": video.get("status")}


@register_node("vidlab7.get_video")
async def vidlab7_get_video(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details of a specific VidLab7 video.

    config:
      api_key  — VidLab7 API key (required)
      video_id — video ID to retrieve (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    video_id = merged.get("video_id")
    if not api_key or not video_id:
        raise ValueError("api_key and video_id are required for vidlab7.get_video")

    async with httpx.AsyncClient(base_url=VIDLAB7_BASE, timeout=30) as client:
        r = await client.get(f"/videos/{video_id}", headers=_vidlab7_headers(api_key))
        r.raise_for_status()
        video = r.json()

    log.info("vidlab7.get_video", video_id=video_id, status=video.get("status"))
    return {"video": video, "video_id": video_id, "status": video.get("status")}


@register_node("vidlab7.list_videos")
async def vidlab7_list_videos(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all videos in your VidLab7 account.

    config:
      api_key — VidLab7 API key (required)
      page    — page number (optional, default 1)
      limit   — results per page (optional, default 20)
      status  — filter by status (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for vidlab7.list_videos")

    params: dict = {"page": merged.get("page", 1), "limit": merged.get("limit", 20)}
    if merged.get("status"):
        params["status"] = merged["status"]

    async with httpx.AsyncClient(base_url=VIDLAB7_BASE, timeout=30) as client:
        r = await client.get("/videos", headers=_vidlab7_headers(api_key), params=params)
        r.raise_for_status()
        data = r.json()

    videos = data.get("data", data) if isinstance(data, dict) else data
    log.info("vidlab7.list_videos", count=len(videos) if isinstance(videos, list) else 1)
    return {"videos": videos, "count": len(videos) if isinstance(videos, list) else None}
