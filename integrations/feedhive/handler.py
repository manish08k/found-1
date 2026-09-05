"""FeedHive AI social media integration — create and list posts."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

FEEDHIVE_BASE = "https://app.feedhive.com/api/v1"


def _headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


@register_node("feedhive.create_post")
async def feedhive_create_post(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new FeedHive post (as draft).

    config/input_data:
      api_key — FeedHive API key (required)
      content — post text content (required)
      type    — post type: draft or published (default: draft)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for feedhive.create_post")
    content = config.get("content") or input_data.get("content")
    if not content:
        raise ValueError("content is required for feedhive.create_post")
    post_type = config.get("type", "draft")

    payload = {"content": content, "type": post_type}

    async with httpx.AsyncClient(base_url=FEEDHIVE_BASE, timeout=30) as client:
        r = await client.post("/posts", headers=_headers(api_key), json=payload)
        r.raise_for_status()
        post = r.json()

    log.info("feedhive.create_post", post_id=post.get("id"), type=post_type)
    return {"post": post, "post_id": post.get("id")}


@register_node("feedhive.list_posts")
async def feedhive_list_posts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List FeedHive published posts.

    config/input_data:
      api_key — FeedHive API key (required)
      status  — post status filter (default: published)
      limit   — max number of posts (default 25)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for feedhive.list_posts")
    status = config.get("status", "published")
    limit = int(config.get("limit", 25))

    async with httpx.AsyncClient(base_url=FEEDHIVE_BASE, timeout=30) as client:
        r = await client.get(
            "/posts",
            headers=_headers(api_key),
            params={"status": status, "limit": limit},
        )
        r.raise_for_status()
        data = r.json()

    posts = data if isinstance(data, list) else data.get("posts", data.get("data", []))
    log.info("feedhive.list_posts", status=status, count=len(posts))
    return {"posts": posts, "count": len(posts), "status": status}
