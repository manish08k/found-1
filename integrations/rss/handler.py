"""RSS integration — read and parse RSS/Atom feeds."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


@register_node("rss.get_feed")
async def rss_get_feed(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    feed_url = merged.get("url", "")
    try:
        import feedparser
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(feed_url)
            r.raise_for_status()
        parsed = feedparser.parse(r.text)
        limit = merged.get("limit", 20)
        entries = []
        for entry in parsed.entries[:limit]:
            entries.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "summary": entry.get("summary", ""),
                "published": entry.get("published", ""),
                "id": entry.get("id", ""),
            })
        return {"feed_title": parsed.feed.get("title", ""), "entries": entries, "count": len(entries)}
    except ImportError:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(feed_url)
            r.raise_for_status()
        return {"raw_content": r.text[:5000], "url": feed_url}


@register_node("rss.parse_entries")
async def rss_parse_entries(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    raw_xml = merged.get("xml", "")
    try:
        import feedparser
        parsed = feedparser.parse(raw_xml)
        return {"entries": [{"title": e.get("title"), "link": e.get("link"), "summary": e.get("summary")} for e in parsed.entries]}
    except ImportError:
        return {"error": "feedparser not installed", "entries": []}
