"""Hacker News integration — top stories, new stories, ask HN, and item details."""
import asyncio
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

HN_BASE = "https://hacker-news.firebaseio.com/v0/"
HN_WEB = "https://news.ycombinator.com/item?id="


async def _fetch_item(client: httpx.AsyncClient, item_id: int) -> dict:
    """Fetch a single HN item by ID."""
    r = await client.get(f"item/{item_id}.json")
    r.raise_for_status()
    return r.json() or {}


async def _fetch_items_batch(client: httpx.AsyncClient, ids: list[int], limit: int) -> list[dict]:
    """Fetch up to `limit` items concurrently."""
    ids = ids[:limit]
    tasks = [_fetch_item(client, iid) for iid in ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    items = []
    for item in results:
        if isinstance(item, dict) and item:
            item["url"] = item.get("url") or f"{HN_WEB}{item.get('id', '')}"
            items.append(item)
    return items


@register_node("hackernews.get_top_stories")
async def hn_get_top_stories(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Fetch the current Hacker News Top Stories.

    config:
      limit        — number of stories to return (default 30, max 500)
      fetch_details — bool, whether to fetch full story details (default True)
    """
    limit = min(int(config.get("limit", 30)), 500)
    fetch_details = config.get("fetch_details", True)

    async with httpx.AsyncClient(base_url=HN_BASE, timeout=30) as client:
        r = await client.get("topstories.json")
        r.raise_for_status()
        ids = r.json() or []

        if fetch_details:
            stories = await _fetch_items_batch(client, ids, limit)
        else:
            stories = [{"id": iid, "url": f"{HN_WEB}{iid}"} for iid in ids[:limit]]

    log.info("hackernews.get_top_stories", count=len(stories), total_available=len(ids))
    return {
        "stories": stories,
        "count": len(stories),
        "total_available": len(ids),
    }


@register_node("hackernews.get_story")
async def hn_get_story(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Fetch a single Hacker News item (story, comment, job, poll, etc.) by ID.

    config/input_data:
      item_id          — HN item ID (required)
      include_comments — bool, fetch top-level comment details (default False)
      comment_limit    — max comments to fetch if include_comments=True (default 10)
    """
    item_id = config.get("item_id") or input_data.get("item_id")
    if not item_id:
        raise ValueError("item_id is required for hackernews.get_story")

    include_comments = bool(config.get("include_comments") or input_data.get("include_comments", False))
    comment_limit = int(config.get("comment_limit", 10))

    async with httpx.AsyncClient(base_url=HN_BASE, timeout=30) as client:
        item = await _fetch_item(client, int(item_id))
        if not item:
            raise ValueError(f"Item {item_id} not found on Hacker News")

        item.setdefault("url", f"{HN_WEB}{item_id}")

        comments = []
        if include_comments and item.get("kids"):
            comments = await _fetch_items_batch(client, item["kids"], comment_limit)

    log.info("hackernews.get_story", item_id=item_id, type=item.get("type"), title=item.get("title"))
    return {
        "item": item,
        "item_id": int(item_id),
        "type": item.get("type"),
        "title": item.get("title"),
        "score": item.get("score"),
        "by": item.get("by"),
        "url": item.get("url"),
        "descendants": item.get("descendants", 0),
        "comments": comments,
    }


@register_node("hackernews.get_new_stories")
async def hn_get_new_stories(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Fetch the most recently submitted Hacker News stories.

    config:
      limit        — number of stories to return (default 30, max 500)
      fetch_details — bool, whether to fetch full story details (default True)
    """
    limit = min(int(config.get("limit", 30)), 500)
    fetch_details = config.get("fetch_details", True)

    async with httpx.AsyncClient(base_url=HN_BASE, timeout=30) as client:
        r = await client.get("newstories.json")
        r.raise_for_status()
        ids = r.json() or []

        if fetch_details:
            stories = await _fetch_items_batch(client, ids, limit)
        else:
            stories = [{"id": iid, "url": f"{HN_WEB}{iid}"} for iid in ids[:limit]]

    log.info("hackernews.get_new_stories", count=len(stories), total_available=len(ids))
    return {
        "stories": stories,
        "count": len(stories),
        "total_available": len(ids),
    }


@register_node("hackernews.get_ask_stories")
async def hn_get_ask_stories(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Fetch Ask HN stories.

    config:
      limit        — number of stories to return (default 30, max 200)
      fetch_details — bool, whether to fetch full story details (default True)
    """
    limit = min(int(config.get("limit", 30)), 200)
    fetch_details = config.get("fetch_details", True)

    async with httpx.AsyncClient(base_url=HN_BASE, timeout=30) as client:
        r = await client.get("askstories.json")
        r.raise_for_status()
        ids = r.json() or []

        if fetch_details:
            stories = await _fetch_items_batch(client, ids, limit)
        else:
            stories = [{"id": iid, "url": f"{HN_WEB}{iid}"} for iid in ids[:limit]]

    log.info("hackernews.get_ask_stories", count=len(stories), total_available=len(ids))
    return {
        "stories": stories,
        "count": len(stories),
        "total_available": len(ids),
    }
