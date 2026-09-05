"""Circle — community platform integration."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

CIRCLE_BASE = "https://app.circle.so/api/v1"


def _headers(config: dict) -> dict:
    api_key = config.get("api_key", "")
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


@register_node("circle.list_members")
async def circle_list_members(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List community members from Circle.

    config:
      api_key  — Circle API key
      per_page — number of members per page (default 25)
    """
    per_page = int(config.get("per_page", 25))

    async with httpx.AsyncClient(base_url=CIRCLE_BASE, timeout=30) as client:
        r = await client.get(
            "/community_members",
            params={"per_page": per_page},
            headers=_headers(config),
        )
        r.raise_for_status()
        data = r.json()

    members = data.get("records", data if isinstance(data, list) else [])
    log.info("circle.list_members", count=len(members))
    return {"members": members, "count": len(members)}


@register_node("circle.get_member")
async def circle_get_member(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single Circle community member by ID.

    config/input_data:
      api_key — Circle API key
      id      — member ID (required)
    """
    member_id = config.get("id") or input_data.get("id")
    if not member_id:
        raise ValueError("id is required for circle.get_member")

    async with httpx.AsyncClient(base_url=CIRCLE_BASE, timeout=30) as client:
        r = await client.get(
            f"/community_members/{member_id}",
            headers=_headers(config),
        )
        r.raise_for_status()
        member = r.json()

    log.info("circle.get_member", member_id=member_id)
    return {"member": member, "id": member_id}


@register_node("circle.list_posts")
async def circle_list_posts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List posts from a Circle community.

    config:
      api_key  — Circle API key
      per_page — number of posts per page (default 25)
    """
    per_page = int(config.get("per_page", 25))

    async with httpx.AsyncClient(base_url=CIRCLE_BASE, timeout=30) as client:
        r = await client.get(
            "/posts",
            params={"per_page": per_page},
            headers=_headers(config),
        )
        r.raise_for_status()
        data = r.json()

    posts = data.get("records", data if isinstance(data, list) else [])
    log.info("circle.list_posts", count=len(posts))
    return {"posts": posts, "count": len(posts)}


@register_node("circle.create_post")
async def circle_create_post(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a post in a Circle community space.

    config/input_data:
      api_key      — Circle API key
      title        — post title (required)
      body         — post body HTML/text (required)
      space_id     — space ID to post into (required)
      community_id — community ID (required)
    """
    title = config.get("title") or input_data.get("title")
    body = config.get("body") or input_data.get("body")
    space_id = config.get("space_id") or input_data.get("space_id")
    community_id = config.get("community_id") or input_data.get("community_id")

    if not title:
        raise ValueError("title is required for circle.create_post")
    if not body:
        raise ValueError("body is required for circle.create_post")
    if not space_id:
        raise ValueError("space_id is required for circle.create_post")
    if not community_id:
        raise ValueError("community_id is required for circle.create_post")

    payload = {
        "name": title,
        "body": body,
        "space_id": space_id,
        "community_id": community_id,
    }

    async with httpx.AsyncClient(base_url=CIRCLE_BASE, timeout=30) as client:
        r = await client.post("/posts", json=payload, headers=_headers(config))
        r.raise_for_status()
        post = r.json()

    log.info("circle.create_post", title=title, space_id=space_id)
    return {"post": post, "id": post.get("id"), "title": title}
