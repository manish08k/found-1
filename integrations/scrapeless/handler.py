"""Scrapeless integration — web scraping and data extraction."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.scrapeless.com/api/v1"


def _headers(config: dict) -> dict:
    return {"x-api-token": config.get("api_key", ""), "Content-Type": "application/json"}


@register_node("scrapeless.scrape_url")
async def scrapeless_scrape_url(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/scraper/request", json={
            "actor": "scraper.request",
            "input": {"url": merged.get("url", ""), "render_js": merged.get("render_js", False)},
        })
        r.raise_for_status()
    return r.json()


@register_node("scrapeless.google_search")
async def scrapeless_google_search(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/scraper/request", json={
            "actor": "scraper.google.search",
            "input": {"q": merged.get("query", ""), "gl": merged.get("country", "us")},
        })
        r.raise_for_status()
    return r.json()
