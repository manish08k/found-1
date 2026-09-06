"""ScrapeGraphAI integration — AI-powered web scraping."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.scrapegraphai.com/v1"


def _headers(config: dict) -> dict:
    return {"SGAI-APIKEY": config.get("api_key", ""), "Content-Type": "application/json"}


@register_node("scrapegrapghai.smartscraper")
async def scrapegrapghai_smartscraper(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/smartscraper", json={
            "website_url": merged.get("url", ""),
            "user_prompt": merged.get("prompt", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("scrapegrapghai.searchgraph")
async def scrapegrapghai_searchgraph(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/searchgraph", json={
            "user_prompt": merged.get("prompt", ""),
            "num_results": merged.get("num_results", 5),
        })
        r.raise_for_status()
    return r.json()
