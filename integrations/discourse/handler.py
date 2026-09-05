"""Discourse forum integration — topics, posts, and user management."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _headers(config: dict) -> dict:
    api_key = config.get("api_key") or ""
    api_username = config.get("api_username") or ""
    if not api_key or not api_username:
        raise ValueError("discourse nodes require 'api_key' and 'api_username' in config")
    return {
        "Api-Key": api_key,
        "Api-Username": api_username,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _base_url(config: dict) -> str:
    base_url = config.get("base_url") or ""
    if not base_url:
        raise ValueError("discourse nodes require 'base_url' in config (e.g. https://forum.example.com)")
    return base_url.rstrip("/")


@register_node("discourse.get_topics")
async def discourse_get_topics(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Fetch the latest topics from the Discourse forum.

    config:
      base_url     — Discourse instance URL, e.g. https://forum.example.com
      api_key      — API key
      api_username — API username (usually 'system' or an admin account)
    """
    merged = {**config, **input_data}
    base = _base_url(merged)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base}/latest.json", headers=_headers(merged))
        r.raise_for_status()
        data = r.json()
    topic_list = data.get("topic_list", {})
    topics = topic_list.get("topics", [])
    log.info("discourse.get_topics", count=len(topics))
    return {"topics": topics, "count": len(topics)}


@register_node("discourse.create_topic")
async def discourse_create_topic(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new topic (post) in the Discourse forum.

    config:
      base_url     — Discourse instance URL
      api_key      — API key
      api_username — API username
      title        — topic title
      raw          — body content (markdown)
      category_id  — optional category ID to post in
    """
    merged = {**config, **input_data}
    title = merged.get("title")
    raw = merged.get("raw")
    if not title:
        raise ValueError("discourse.create_topic requires 'title'")
    if not raw:
        raise ValueError("discourse.create_topic requires 'raw' body content")
    base = _base_url(merged)
    payload: dict = {"title": title, "raw": raw}
    category_id = merged.get("category_id")
    if category_id:
        payload["category"] = int(category_id)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{base}/posts.json", json=payload, headers=_headers(merged))
        r.raise_for_status()
        data = r.json()
    log.info("discourse.create_topic", topic_id=data.get("topic_id"), title=title)
    return {"post": data, "topic_id": data.get("topic_id"), "ok": True}


@register_node("discourse.get_topic")
async def discourse_get_topic(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a specific Discourse topic by ID.

    config:
      base_url     — Discourse instance URL
      api_key      — API key
      api_username — API username
      topic_id     — ID of the topic to retrieve
    """
    merged = {**config, **input_data}
    topic_id = merged.get("topic_id")
    if not topic_id:
        raise ValueError("discourse.get_topic requires 'topic_id'")
    base = _base_url(merged)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base}/t/{topic_id}.json", headers=_headers(merged))
        r.raise_for_status()
        data = r.json()
    log.info("discourse.get_topic", topic_id=topic_id, title=data.get("title"))
    return {"topic": data}


@register_node("discourse.create_post")
async def discourse_create_post(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a reply post on an existing Discourse topic.

    config:
      base_url     — Discourse instance URL
      api_key      — API key
      api_username — API username
      topic_id     — ID of the topic to reply to
      raw          — body content (markdown)
    """
    merged = {**config, **input_data}
    topic_id = merged.get("topic_id")
    raw = merged.get("raw")
    if not topic_id:
        raise ValueError("discourse.create_post requires 'topic_id'")
    if not raw:
        raise ValueError("discourse.create_post requires 'raw' body content")
    base = _base_url(merged)
    payload = {"topic_id": int(topic_id), "raw": raw}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{base}/posts.json", json=payload, headers=_headers(merged))
        r.raise_for_status()
        data = r.json()
    log.info("discourse.create_post", topic_id=topic_id, post_id=data.get("id"))
    return {"post": data, "post_id": data.get("id"), "ok": True}


@register_node("discourse.get_user")
async def discourse_get_user(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a Discourse user's public profile by username.

    config:
      base_url     — Discourse instance URL
      api_key      — API key
      api_username — API username (for auth, not the target user)
      username     — username of the profile to retrieve
    """
    merged = {**config, **input_data}
    username = merged.get("username")
    if not username:
        raise ValueError("discourse.get_user requires 'username'")
    base = _base_url(merged)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base}/u/{username}.json", headers=_headers(merged))
        r.raise_for_status()
        data = r.json()
    user = data.get("user", data)
    log.info("discourse.get_user", username=username)
    return {"user": user}
