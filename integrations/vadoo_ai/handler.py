"""Vadoo AI video creation and hosting — handler for vadoo_ai integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.vadoo.tv/v1"


@register_node("vadoo_ai.create_video")
async def vadoo_ai_create_video(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a video from text/script.

    config/input_data:
      api_key — API key or token (required)
      script — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    script = merged.get("script") or ""
    if not script:
        raise ValueError("script required for vadoo_ai.create_video")
    payload = {"script": script}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/videos", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("vadoo_ai.create_video")
    return {"data": data}

@register_node("vadoo_ai.get_video")
async def vadoo_ai_get_video(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get video status.

    config/input_data:
      api_key — API key or token (required)
      video_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    video_id = merged.get("video_id") or ""
    if not video_id:
        raise ValueError("video_id required for vadoo_ai.get_video")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/videos/{video_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("vadoo_ai.get_video")
    return {"data": data}

@register_node("vadoo_ai.list_videos")
async def vadoo_ai_list_videos(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all videos.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/videos", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("vadoo_ai.list_videos")
    return {"data": data}
