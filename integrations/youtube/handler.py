"""YouTube Data API v3 integration — search, videos, channels."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

YOUTUBE_BASE = "https://www.googleapis.com/youtube/v3"


def _headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


@register_node("youtube.search")
async def youtube_search(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Search YouTube videos by query.

    config/input_data:
      access_token — OAuth2 Bearer token (required)
      query        — search query string (required)
      max_results  — max number of results (default 10)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for youtube.search")
    query = config.get("query") or input_data.get("query")
    if not query:
        raise ValueError("query is required for youtube.search")
    max_results = int(config.get("max_results", 10))

    params = {
        "part": "snippet",
        "q": query,
        "maxResults": max_results,
        "type": "video",
    }

    async with httpx.AsyncClient(base_url=YOUTUBE_BASE, timeout=30) as client:
        r = await client.get("/search", headers=_headers(access_token), params=params)
        r.raise_for_status()
        data = r.json()

    items = data.get("items", [])
    log.info("youtube.search", query=query, count=len(items))
    return {
        "items": items,
        "count": len(items),
        "page_info": data.get("pageInfo", {}),
        "next_page_token": data.get("nextPageToken"),
    }


@register_node("youtube.get_video")
async def youtube_get_video(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get video details by ID.

    config/input_data:
      access_token — OAuth2 Bearer token (required)
      video_id     — YouTube video ID (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for youtube.get_video")
    video_id = config.get("video_id") or input_data.get("video_id")
    if not video_id:
        raise ValueError("video_id is required for youtube.get_video")

    params = {"part": "snippet,statistics", "id": video_id}

    async with httpx.AsyncClient(base_url=YOUTUBE_BASE, timeout=30) as client:
        r = await client.get("/videos", headers=_headers(access_token), params=params)
        r.raise_for_status()
        data = r.json()

    items = data.get("items", [])
    video = items[0] if items else {}
    log.info("youtube.get_video", video_id=video_id, found=bool(video))
    return {"video": video, "video_id": video_id}


@register_node("youtube.list_channel_videos")
async def youtube_list_channel_videos(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List videos from a YouTube channel.

    config/input_data:
      access_token — OAuth2 Bearer token (required)
      channel_id   — YouTube channel ID (required)
      max_results  — max number of results (default 25)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for youtube.list_channel_videos")
    channel_id = config.get("channel_id") or input_data.get("channel_id")
    if not channel_id:
        raise ValueError("channel_id is required for youtube.list_channel_videos")
    max_results = int(config.get("max_results", 25))

    params = {
        "part": "snippet",
        "channelId": channel_id,
        "type": "video",
        "maxResults": max_results,
    }

    async with httpx.AsyncClient(base_url=YOUTUBE_BASE, timeout=30) as client:
        r = await client.get("/search", headers=_headers(access_token), params=params)
        r.raise_for_status()
        data = r.json()

    items = data.get("items", [])
    log.info("youtube.list_channel_videos", channel_id=channel_id, count=len(items))
    return {
        "items": items,
        "count": len(items),
        "channel_id": channel_id,
        "page_info": data.get("pageInfo", {}),
        "next_page_token": data.get("nextPageToken"),
    }


@register_node("youtube.get_channel")
async def youtube_get_channel(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get channel details by channel ID.

    config/input_data:
      access_token — OAuth2 Bearer token (required)
      channel_id   — YouTube channel ID (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for youtube.get_channel")
    channel_id = config.get("channel_id") or input_data.get("channel_id")
    if not channel_id:
        raise ValueError("channel_id is required for youtube.get_channel")

    params = {"part": "snippet,statistics", "id": channel_id}

    async with httpx.AsyncClient(base_url=YOUTUBE_BASE, timeout=30) as client:
        r = await client.get("/channels", headers=_headers(access_token), params=params)
        r.raise_for_status()
        data = r.json()

    items = data.get("items", [])
    channel = items[0] if items else {}
    log.info("youtube.get_channel", channel_id=channel_id, found=bool(channel))
    return {"channel": channel, "channel_id": channel_id}
