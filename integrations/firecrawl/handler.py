"""Firecrawl integration — web scraping and crawling."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.firecrawl.dev/v0"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("firecrawl.scrape_url")
async def firecrawl_scrape_url(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/scrape", json={
            "url": merged.get("url", ""),
            "pageOptions": {"onlyMainContent": merged.get("only_main_content", True)},
        })
        r.raise_for_status()
    return r.json()


@register_node("firecrawl.crawl_website")
async def firecrawl_crawl_website(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/crawl", json={
            "url": merged.get("url", ""),
            "crawlerOptions": {"maxDepth": merged.get("max_depth", 2), "limit": merged.get("limit", 10)},
        })
        r.raise_for_status()
    return r.json()


@register_node("firecrawl.search")
async def firecrawl_search(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/search", json={"query": merged.get("query", ""), "limit": merged.get("limit", 5)})
        r.raise_for_status()
    return r.json()
