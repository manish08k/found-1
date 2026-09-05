"""Vimeo API integration — video listing, retrieval, update, delete."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

VIMEO_BASE = "https://api.vimeo.com"


def _headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


@register_node("vimeo.list_videos")
async def vimeo_list_videos(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List the authenticated Vimeo user's videos.

    config/input_data:
      access_token — OAuth2 Bearer token (required)
      per_page     — number of videos per page (default 25)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for vimeo.list_videos")
    per_page = int(config.get("per_page", 25))

    async with httpx.AsyncClient(base_url=VIMEO_BASE, timeout=30) as client:
        r = await client.get("/me/videos", headers=_headers(access_token), params={"per_page": per_page})
        r.raise_for_status()
        data = r.json()

    items = data.get("data", [])
    log.info("vimeo.list_videos", count=len(items), total=data.get("total"))
    return {
        "videos": items,
        "count": len(items),
        "total": data.get("total"),
        "paging": data.get("paging", {}),
    }


@register_node("vimeo.get_video")
async def vimeo_get_video(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get Vimeo video details by video ID.

    config/input_data:
      access_token — OAuth2 Bearer token (required)
      video_id     — Vimeo video ID (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for vimeo.get_video")
    video_id = config.get("video_id") or input_data.get("video_id")
    if not video_id:
        raise ValueError("video_id is required for vimeo.get_video")

    async with httpx.AsyncClient(base_url=VIMEO_BASE, timeout=30) as client:
        r = await client.get(f"/videos/{video_id}", headers=_headers(access_token))
        r.raise_for_status()
        video = r.json()

    log.info("vimeo.get_video", video_id=video_id, name=video.get("name"))
    return {"video": video, "video_id": video_id}


@register_node("vimeo.update_video")
async def vimeo_update_video(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update Vimeo video metadata.

    config/input_data:
      access_token — OAuth2 Bearer token (required)
      video_id     — Vimeo video ID (required)
      title        — new video title (optional)
      description  — new video description (optional)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for vimeo.update_video")
    video_id = config.get("video_id") or input_data.get("video_id")
    if not video_id:
        raise ValueError("video_id is required for vimeo.update_video")

    payload = {}
    title = config.get("title") or input_data.get("title")
    description = config.get("description") or input_data.get("description")
    if title:
        payload["name"] = title
    if description:
        payload["description"] = description

    async with httpx.AsyncClient(base_url=VIMEO_BASE, timeout=30) as client:
        r = await client.patch(f"/videos/{video_id}", headers=_headers(access_token), json=payload)
        r.raise_for_status()
        video = r.json()

    log.info("vimeo.update_video", video_id=video_id)
    return {"video": video, "video_id": video_id}


@register_node("vimeo.delete_video")
async def vimeo_delete_video(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete a Vimeo video.

    config/input_data:
      access_token — OAuth2 Bearer token (required)
      video_id     — Vimeo video ID (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for vimeo.delete_video")
    video_id = config.get("video_id") or input_data.get("video_id")
    if not video_id:
        raise ValueError("video_id is required for vimeo.delete_video")

    async with httpx.AsyncClient(base_url=VIMEO_BASE, timeout=30) as client:
        r = await client.delete(f"/videos/{video_id}", headers=_headers(access_token))
        r.raise_for_status()

    log.info("vimeo.delete_video", video_id=video_id)
    return {"deleted": True, "video_id": video_id}
