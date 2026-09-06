"""Facebook Pages integration — page posts, insights, messages."""
import httpx
import structlog
from core.execution_engine import register_node
from oauth.flow import get_access_token

log = structlog.get_logger(__name__)
BASE = "https://graph.facebook.com/v18.0"


async def _token(credential_id: str, db) -> str:
    return await get_access_token(credential_id, db)


@register_node("facebook_pages.create_post")
async def fb_pages_create_post(config: dict, input_data: dict, credential_id: str, db) -> dict:
    token = await _token(credential_id, db)
    page_id = config.get("page_id") or input_data.get("page_id", "me")
    message = config.get("message") or input_data.get("message", "")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE}/{page_id}/feed", data={
            "message": message, "access_token": token
        })
        r.raise_for_status()
    return r.json()


@register_node("facebook_pages.get_page_insights")
async def fb_pages_get_insights(config: dict, input_data: dict, credential_id: str, db) -> dict:
    token = await _token(credential_id, db)
    page_id = config.get("page_id") or input_data.get("page_id", "me")
    metric = config.get("metric", "page_impressions")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE}/{page_id}/insights/{metric}", params={"access_token": token})
        r.raise_for_status()
    return r.json()


@register_node("facebook_pages.get_posts")
async def fb_pages_get_posts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    token = await _token(credential_id, db)
    page_id = config.get("page_id") or input_data.get("page_id", "me")
    limit = config.get("limit", 10)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE}/{page_id}/posts", params={"access_token": token, "limit": limit})
        r.raise_for_status()
    return r.json()
