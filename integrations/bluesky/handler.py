"""Bluesky integration — social network via AT Protocol / Bluesky API."""
from datetime import datetime, timezone
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BSKY_BASE = "https://bsky.social/xrpc"


async def _create_session(config: dict, input_data: dict) -> dict:
    """Authenticate with Bluesky and return session data (accessJwt, did, handle)."""
    merged = {**config, **input_data}
    identifier = merged.get("identifier", "") or merged.get("handle", "")
    password = merged.get("password", "")
    if not identifier or not password:
        raise ValueError("identifier and password are required for Bluesky")
    payload = {"identifier": identifier, "password": password}
    async with httpx.AsyncClient(base_url=BSKY_BASE, timeout=30) as client:
        r = await client.post("/com.atproto.server.createSession", json=payload)
        r.raise_for_status()
        return r.json()


@register_node("bluesky.create_post")
async def create_post(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a post on Bluesky.

    config/input_data:
      identifier — Bluesky handle or DID (required)
      password   — Bluesky app password (required)
      text       — Post text content (required)
    """
    merged = {**config, **input_data}
    text = merged.get("text", "")
    if not text:
        raise ValueError("text is required for bluesky.create_post")
    session = await _create_session(config, input_data)
    access_jwt = session.get("accessJwt", "")
    did = session.get("did", "")
    headers = {"Authorization": f"Bearer {access_jwt}"}
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = {
        "repo": did,
        "collection": "app.bsky.feed.post",
        "record": {"text": text, "createdAt": now_iso},
    }
    async with httpx.AsyncClient(base_url=BSKY_BASE, timeout=30) as client:
        r = await client.post("/com.atproto.repo.createRecord", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("bluesky.create_post", did=did)
    return {"result": data, "did": did, "text": text}


@register_node("bluesky.get_timeline")
async def get_timeline(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get the home timeline from Bluesky.

    config/input_data:
      identifier — Bluesky handle or DID (required)
      password   — Bluesky app password (required)
    """
    session = await _create_session(config, input_data)
    access_jwt = session.get("accessJwt", "")
    headers = {"Authorization": f"Bearer {access_jwt}"}
    async with httpx.AsyncClient(base_url=BSKY_BASE, timeout=30) as client:
        r = await client.get(
            "/app.bsky.feed.getTimeline",
            params={"limit": 20},
            headers=headers,
        )
        r.raise_for_status()
        data = r.json()
    feed = data.get("feed", [])
    log.info("bluesky.get_timeline", count=len(feed))
    return {"feed": feed, "count": len(feed)}


@register_node("bluesky.search_posts")
async def search_posts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Search posts on Bluesky.

    config/input_data:
      identifier — Bluesky handle or DID (required)
      password   — Bluesky app password (required)
      query      — Search query (required)
    """
    merged = {**config, **input_data}
    query = merged.get("query", "") or merged.get("q", "")
    if not query:
        raise ValueError("query is required for bluesky.search_posts")
    session = await _create_session(config, input_data)
    access_jwt = session.get("accessJwt", "")
    headers = {"Authorization": f"Bearer {access_jwt}"}
    async with httpx.AsyncClient(base_url=BSKY_BASE, timeout=30) as client:
        r = await client.get(
            "/app.bsky.feed.searchPosts",
            params={"q": query},
            headers=headers,
        )
        r.raise_for_status()
        data = r.json()
    posts = data.get("posts", [])
    log.info("bluesky.search_posts", query=query, count=len(posts))
    return {"posts": posts, "count": len(posts), "query": query}
