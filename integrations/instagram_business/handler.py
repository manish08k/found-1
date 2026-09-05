"""Instagram Business API integration — media, insights, content publishing."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

INSTAGRAM_BASE = "https://graph.facebook.com/v18.0"


@register_node("instagram_business.list_media")
async def instagram_list_media(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List Instagram Business media objects for a user.

    config/input_data:
      access_token — Facebook/Instagram access token (required)
      user_id      — Instagram Business account user ID (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for instagram_business.list_media")
    user_id = config.get("user_id") or input_data.get("user_id")
    if not user_id:
        raise ValueError("user_id is required for instagram_business.list_media")

    params = {
        "fields": "id,caption,media_type,timestamp",
        "access_token": access_token,
    }

    async with httpx.AsyncClient(base_url=INSTAGRAM_BASE, timeout=30) as client:
        r = await client.get(f"/{user_id}/media", params=params)
        r.raise_for_status()
        data = r.json()

    items = data.get("data", [])
    log.info("instagram_business.list_media", user_id=user_id, count=len(items))
    return {
        "media": items,
        "count": len(items),
        "user_id": user_id,
        "paging": data.get("paging", {}),
    }


@register_node("instagram_business.get_insights")
async def instagram_get_insights(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get Instagram Business account insights.

    config/input_data:
      access_token — Facebook/Instagram access token (required)
      user_id      — Instagram Business account user ID (required)
      metric       — comma-separated metrics (default: impressions,reach)
      period       — period for metrics (default: day)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for instagram_business.get_insights")
    user_id = config.get("user_id") or input_data.get("user_id")
    if not user_id:
        raise ValueError("user_id is required for instagram_business.get_insights")
    metric = config.get("metric", "impressions,reach")
    period = config.get("period", "day")

    params = {
        "metric": metric,
        "period": period,
        "access_token": access_token,
    }

    async with httpx.AsyncClient(base_url=INSTAGRAM_BASE, timeout=30) as client:
        r = await client.get(f"/{user_id}/insights", params=params)
        r.raise_for_status()
        data = r.json()

    items = data.get("data", [])
    log.info("instagram_business.get_insights", user_id=user_id, metric=metric, count=len(items))
    return {
        "insights": items,
        "count": len(items),
        "user_id": user_id,
        "paging": data.get("paging", {}),
    }


@register_node("instagram_business.create_media")
async def instagram_create_media(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create an Instagram Business media container for publishing.

    config/input_data:
      access_token — Facebook/Instagram access token (required)
      user_id      — Instagram Business account user ID (required)
      image_url    — public URL of the image (required)
      caption      — caption text (optional)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for instagram_business.create_media")
    user_id = config.get("user_id") or input_data.get("user_id")
    if not user_id:
        raise ValueError("user_id is required for instagram_business.create_media")
    image_url = config.get("image_url") or input_data.get("image_url")
    if not image_url:
        raise ValueError("image_url is required for instagram_business.create_media")

    payload = {
        "image_url": image_url,
        "caption": config.get("caption") or input_data.get("caption", ""),
        "access_token": access_token,
    }

    async with httpx.AsyncClient(base_url=INSTAGRAM_BASE, timeout=30) as client:
        r = await client.post(f"/{user_id}/media", json=payload)
        r.raise_for_status()
        result = r.json()

    media_id = result.get("id")
    log.info("instagram_business.create_media", user_id=user_id, media_id=media_id)
    return {"result": result, "media_id": media_id, "user_id": user_id}
