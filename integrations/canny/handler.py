"""Canny — product feedback and feature request integration."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

CANNY_BASE = "https://canny.io/api/v1"


@register_node("canny.list_posts")
async def canny_list_posts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List posts from a Canny board.

    config/input_data:
      api_key  — Canny API key
      board_id — board ID to list posts from (required)
    """
    api_key = config.get("api_key", "")
    board_id = config.get("board_id") or input_data.get("board_id")

    if not board_id:
        raise ValueError("board_id is required for canny.list_posts")

    async with httpx.AsyncClient(base_url=CANNY_BASE, timeout=30) as client:
        r = await client.post(
            "/posts/list",
            json={"apiKey": api_key, "boardID": board_id},
            headers={"Content-Type": "application/json"},
        )
        r.raise_for_status()
        data = r.json()

    posts = data.get("posts", data if isinstance(data, list) else [])
    log.info("canny.list_posts", board_id=board_id, count=len(posts))
    return {"posts": posts, "count": len(posts), "board_id": board_id}


@register_node("canny.list_boards")
async def canny_list_boards(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all boards in a Canny account.

    config:
      api_key — Canny API key
    """
    api_key = config.get("api_key", "")

    async with httpx.AsyncClient(base_url=CANNY_BASE, timeout=30) as client:
        r = await client.post(
            "/boards/list",
            json={"apiKey": api_key},
            headers={"Content-Type": "application/json"},
        )
        r.raise_for_status()
        data = r.json()

    boards = data.get("boards", data if isinstance(data, list) else [])
    log.info("canny.list_boards", count=len(boards))
    return {"boards": boards, "count": len(boards)}


@register_node("canny.create_post")
async def canny_create_post(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new post on a Canny board.

    config/input_data:
      api_key   — Canny API key
      author_id — author user ID (required)
      board_id  — board ID to create post on (required)
      title     — post title (required)
      details   — post details/description (optional)
    """
    api_key = config.get("api_key", "")
    author_id = config.get("author_id") or input_data.get("author_id")
    board_id = config.get("board_id") or input_data.get("board_id")
    title = config.get("title") or input_data.get("title")
    details = config.get("details") or input_data.get("details", "")

    if not author_id:
        raise ValueError("author_id is required for canny.create_post")
    if not board_id:
        raise ValueError("board_id is required for canny.create_post")
    if not title:
        raise ValueError("title is required for canny.create_post")

    async with httpx.AsyncClient(base_url=CANNY_BASE, timeout=30) as client:
        r = await client.post(
            "/posts/create",
            json={
                "apiKey": api_key,
                "authorID": author_id,
                "boardID": board_id,
                "title": title,
                "details": details,
            },
            headers={"Content-Type": "application/json"},
        )
        r.raise_for_status()
        post = r.json()

    log.info("canny.create_post", board_id=board_id, title=title)
    return {"post": post, "id": post.get("id"), "title": title}


@register_node("canny.change_post_status")
async def canny_change_post_status(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Change the status of a Canny post.

    config/input_data:
      api_key    — Canny API key
      changer_id — user ID of the person changing status (required)
      post_id    — post ID to update (required)
      status     — new status string, e.g. "planned", "in progress", "complete" (required)
    """
    api_key = config.get("api_key", "")
    changer_id = config.get("changer_id") or input_data.get("changer_id")
    post_id = config.get("post_id") or input_data.get("post_id")
    status = config.get("status") or input_data.get("status")

    if not changer_id:
        raise ValueError("changer_id is required for canny.change_post_status")
    if not post_id:
        raise ValueError("post_id is required for canny.change_post_status")
    if not status:
        raise ValueError("status is required for canny.change_post_status")

    async with httpx.AsyncClient(base_url=CANNY_BASE, timeout=30) as client:
        r = await client.post(
            "/posts/changeStatus",
            json={
                "apiKey": api_key,
                "changerID": changer_id,
                "postID": post_id,
                "status": status,
            },
            headers={"Content-Type": "application/json"},
        )
        r.raise_for_status()
        result = r.json()

    log.info("canny.change_post_status", post_id=post_id, status=status)
    return {"result": result, "post_id": post_id, "status": status}
