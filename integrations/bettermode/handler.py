"""Bettermode — community platform GraphQL integration."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BETTERMODE_BASE = "https://api.bettermode.com"


def _headers(config: dict) -> dict:
    api_key = config.get("api_key", "")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


@register_node("bettermode.list_members")
async def bettermode_list_members(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List members from a Bettermode community via GraphQL.

    config:
      api_key — Bettermode API key
      limit   — number of members to return (default 25)
    """
    limit = int(config.get("limit", 25))

    query = """
    query ListMembers($limit: Int) {
      members(limit: $limit) {
        nodes {
          id
          name
          email
          role { name }
          createdAt
        }
        totalCount
      }
    }
    """

    async with httpx.AsyncClient(base_url=BETTERMODE_BASE, timeout=30) as client:
        r = await client.post(
            "/graphql",
            json={"query": query, "variables": {"limit": limit}},
            headers=_headers(config),
        )
        r.raise_for_status()
        data = r.json()

    if "errors" in data:
        raise ValueError(f"Bettermode GraphQL error: {data['errors']}")

    members_data = data.get("data", {}).get("members", {})
    members = members_data.get("nodes", [])
    log.info("bettermode.list_members", count=len(members))
    return {
        "members": members,
        "count": len(members),
        "total_count": members_data.get("totalCount", len(members)),
    }


@register_node("bettermode.create_post")
async def bettermode_create_post(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a post in a Bettermode community space via GraphQL.

    config/input_data:
      api_key  — Bettermode API key
      title    — post title (required)
      content  — post content (required)
      space_id — target space ID (required)
    """
    title = config.get("title") or input_data.get("title")
    content = config.get("content") or input_data.get("content")
    space_id = config.get("space_id") or input_data.get("space_id")

    if not title:
        raise ValueError("title is required for bettermode.create_post")
    if not content:
        raise ValueError("content is required for bettermode.create_post")
    if not space_id:
        raise ValueError("space_id is required for bettermode.create_post")

    mutation = """
    mutation CreatePost($spaceId: ID!, $title: String!, $content: String!) {
      createPost(spaceId: $spaceId, input: { title: $title, content: $content }) {
        id
        title
        url
        createdAt
      }
    }
    """

    async with httpx.AsyncClient(base_url=BETTERMODE_BASE, timeout=30) as client:
        r = await client.post(
            "/graphql",
            json={
                "query": mutation,
                "variables": {"spaceId": space_id, "title": title, "content": content},
            },
            headers=_headers(config),
        )
        r.raise_for_status()
        data = r.json()

    if "errors" in data:
        raise ValueError(f"Bettermode GraphQL error: {data['errors']}")

    post = data.get("data", {}).get("createPost", {})
    log.info("bettermode.create_post", title=title, space_id=space_id)
    return {"post": post, "id": post.get("id"), "title": title}
