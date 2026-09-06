"""Beamer product changelog and notification — handler for beamer integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.getbeamer.com/v0"


@register_node("beamer.list_posts")
async def beamer_list_posts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List changelog posts.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/posts", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("beamer.list_posts")
    return {"data": data}

@register_node("beamer.create_post")
async def beamer_create_post(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a changelog post.

    config/input_data:
      api_key — API key or token (required)
      title — (required)
      content — (required)
      category — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    title = merged.get("title") or ""
    content = merged.get("content") or ""
    category = merged.get("category") or ""
    if not title or not content or not category:
        raise ValueError("title, content, category required for beamer.create_post")
    payload = {"title": title, "content": content, "category": category}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/posts", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("beamer.create_post")
    return {"data": data}

@register_node("beamer.get_post")
async def beamer_get_post(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a post.

    config/input_data:
      api_key — API key or token (required)
      post_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    post_id = merged.get("post_id") or ""
    if not post_id:
        raise ValueError("post_id required for beamer.get_post")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/posts/{post_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("beamer.get_post")
    return {"data": data}
