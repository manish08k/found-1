"""AppFollow app store review management — handler for appfollow integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.appfollow.io/api/v2"


@register_node("appfollow.list_apps")
async def appfollow_list_apps(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List tracked apps.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/apps", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("appfollow.list_apps")
    return {"data": data}

@register_node("appfollow.get_reviews")
async def appfollow_get_reviews(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get app reviews.

    config/input_data:
      api_key — API key or token (required)
      app_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    app_id = merged.get("app_id") or ""
    if not app_id:
        raise ValueError("app_id required for appfollow.get_reviews")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/apps/{app_id}/reviews", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("appfollow.get_reviews")
    return {"data": data}

@register_node("appfollow.reply_review")
async def appfollow_reply_review(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Reply to a review.

    config/input_data:
      api_key — API key or token (required)
      app_id — (required)
      review_id — (required)
      text — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    app_id = merged.get("app_id") or ""
    review_id = merged.get("review_id") or ""
    text = merged.get("text") or ""
    if not app_id or not review_id or not text:
        raise ValueError("app_id, review_id, text required for appfollow.reply_review")
    payload = {"text": text}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/apps/{app_id}/reviews/{review_id}/reply", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("appfollow.reply_review")
    return {"data": data}
