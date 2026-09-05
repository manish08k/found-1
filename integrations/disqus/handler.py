"""Disqus integration — thread and post management via the Disqus REST API."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

DISQUS_BASE = "https://disqus.com/api/3.0"


def _access_token(config: dict) -> str:
    token = config.get("access_token") or ""
    if not token:
        raise ValueError("disqus nodes require 'access_token' in config")
    return token


def _api_key(config: dict) -> str:
    key = config.get("api_key") or ""
    if not key:
        raise ValueError("disqus nodes require 'api_key' in config")
    return key


@register_node("disqus.list_threads")
async def disqus_list_threads(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List threads for a Disqus forum.

    config:
      access_token — OAuth access token
      api_key      — Disqus public API key
      forum        — Disqus forum short name
    """
    merged = {**config, **input_data}
    forum = merged.get("forum")
    if not forum:
        raise ValueError("disqus.list_threads requires 'forum'")
    params = {
        "forum": forum,
        "access_token": _access_token(merged),
        "api_key": _api_key(merged),
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{DISQUS_BASE}/threads/list.json", params=params)
        r.raise_for_status()
        data = r.json()
    threads = data.get("response", [])
    log.info("disqus.list_threads", forum=forum, count=len(threads))
    return {"threads": threads, "count": len(threads), "cursor": data.get("cursor")}


@register_node("disqus.create_thread")
async def disqus_create_thread(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new Disqus thread.

    config:
      access_token — OAuth access token
      api_key      — Disqus public API key
      forum        — Disqus forum short name
      title        — thread title
      url          — URL of the page the thread belongs to
    """
    merged = {**config, **input_data}
    forum = merged.get("forum")
    title = merged.get("title")
    url = merged.get("url")
    if not forum:
        raise ValueError("disqus.create_thread requires 'forum'")
    if not title:
        raise ValueError("disqus.create_thread requires 'title'")
    payload = {
        "forum": forum,
        "title": title,
        "access_token": _access_token(merged),
        "api_key": _api_key(merged),
    }
    if url:
        payload["url"] = url
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{DISQUS_BASE}/threads/create.json", data=payload)
        r.raise_for_status()
        data = r.json()
    thread = data.get("response", {})
    log.info("disqus.create_thread", forum=forum, title=title, thread_id=thread.get("id"))
    return {"thread": thread, "ok": True}


@register_node("disqus.list_posts")
async def disqus_list_posts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List posts (comments) on a Disqus thread.

    config:
      access_token — OAuth access token
      api_key      — Disqus public API key
      thread       — Disqus thread ID
    """
    merged = {**config, **input_data}
    thread_id = merged.get("thread") or merged.get("thread_id")
    if not thread_id:
        raise ValueError("disqus.list_posts requires 'thread' (thread ID)")
    params = {
        "thread": thread_id,
        "access_token": _access_token(merged),
        "api_key": _api_key(merged),
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{DISQUS_BASE}/posts/list.json", params=params)
        r.raise_for_status()
        data = r.json()
    posts = data.get("response", [])
    log.info("disqus.list_posts", thread_id=thread_id, count=len(posts))
    return {"posts": posts, "count": len(posts), "cursor": data.get("cursor")}


@register_node("disqus.create_post")
async def disqus_create_post(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new post (comment) on a Disqus thread.

    config:
      access_token — OAuth access token
      api_key      — Disqus public API key
      thread       — Disqus thread ID to post on
      message      — text content of the post
    """
    merged = {**config, **input_data}
    thread_id = merged.get("thread") or merged.get("thread_id")
    message = merged.get("message")
    if not thread_id:
        raise ValueError("disqus.create_post requires 'thread' (thread ID)")
    if not message:
        raise ValueError("disqus.create_post requires 'message'")
    payload = {
        "thread": thread_id,
        "message": message,
        "access_token": _access_token(merged),
        "api_key": _api_key(merged),
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{DISQUS_BASE}/posts/create.json", data=payload)
        r.raise_for_status()
        data = r.json()
    post = data.get("response", {})
    log.info("disqus.create_post", thread_id=thread_id, post_id=post.get("id"))
    return {"post": post, "ok": True}
