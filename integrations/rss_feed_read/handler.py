"""RssFeedRead integration — read and parse RSS/Atom feeds.

No credentials required.

Nodes:
  - rss_feed_read.read : fetch and parse a feed URL, returning entries

Config:
  - url   : the feed URL (required)
  - limit : max number of entries to return (default: 10)
"""
import xml.etree.ElementTree as ET
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data  # noqa: F401 — standard import

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Library import with fallback
# ---------------------------------------------------------------------------
try:
    import feedparser  # type: ignore
    _FEED_BACKEND = "feedparser"
except ImportError:
    feedparser = None  # type: ignore
    _FEED_BACKEND = "xml.etree"


# ---------------------------------------------------------------------------
# Fallback XML parser
# ---------------------------------------------------------------------------

def _parse_feed_xml(content: bytes) -> dict:
    """Minimal RSS/Atom parser using stdlib xml.etree.ElementTree."""
    root = ET.fromstring(content)

    # Detect format
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entries = []

    # RSS 2.0
    channel = root.find("channel")
    if channel is not None:
        feed_title = (channel.findtext("title") or "").strip()
        for item in channel.findall("item"):
            entries.append({
                "title": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "description": (item.findtext("description") or "").strip(),
                "published": (item.findtext("pubDate") or "").strip(),
                "id": (item.findtext("guid") or "").strip(),
            })
        return {"title": feed_title, "entries": entries}

    # Atom
    feed_title = (root.findtext("atom:title", namespaces=ns) or "").strip()
    for entry in root.findall("atom:entry", namespaces=ns):
        link_el = entry.find("atom:link", namespaces=ns)
        link = link_el.get("href", "") if link_el is not None else ""
        entries.append({
            "title": (entry.findtext("atom:title", namespaces=ns) or "").strip(),
            "link": link,
            "description": (entry.findtext("atom:summary", namespaces=ns) or "").strip(),
            "published": (entry.findtext("atom:updated", namespaces=ns) or "").strip(),
            "id": (entry.findtext("atom:id", namespaces=ns) or "").strip(),
        })
    return {"title": feed_title, "entries": entries}


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

@register_node("rss_feed_read.read")
async def read_feed(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Fetch and parse an RSS or Atom feed."""
    url = config.get("url") or input_data.get("url")
    if not url:
        raise ValueError("'url' is required")
    limit = int(config.get("limit", input_data.get("limit", 10)))

    log.info("rss_feed_read.read", url=url, limit=limit, backend=_FEED_BACKEND)

    if _FEED_BACKEND == "feedparser":
        # feedparser can parse directly from URL but we fetch with httpx for
        # consistent timeout/proxy behaviour
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
            raw = r.text

        parsed = feedparser.parse(raw)
        feed_title = parsed.feed.get("title", "")
        entries = []
        for entry in parsed.entries[:limit]:
            entries.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "description": entry.get("summary", ""),
                "published": entry.get("published", ""),
                "id": entry.get("id", ""),
            })
        result = {
            "title": feed_title,
            "entries": entries,
            "entry_count": len(entries),
            "backend": _FEED_BACKEND,
            "url": url,
        }
    else:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
            raw_bytes = r.content

        parsed = _parse_feed_xml(raw_bytes)
        entries = parsed["entries"][:limit]
        result = {
            "title": parsed.get("title", ""),
            "entries": entries,
            "entry_count": len(entries),
            "backend": _FEED_BACKEND,
            "url": url,
        }

    log.info("rss_feed_read.read.done", entry_count=result["entry_count"])
    return result
