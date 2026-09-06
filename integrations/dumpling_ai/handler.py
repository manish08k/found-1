"""Dumpling AI integration — data collection and extraction."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://app.dumplingai.com/api/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("dumpling_ai.scrape_url")
async def dumpling_ai_scrape_url(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/scrape", json={"url": merged.get("url", "")})
        r.raise_for_status()
    return r.json()


@register_node("dumpling_ai.search_web")
async def dumpling_ai_search_web(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/search", json={"query": merged.get("query", "")})
        r.raise_for_status()
    return r.json()


@register_node("dumpling_ai.extract_data")
async def dumpling_ai_extract_data(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/extract", json={
            "url": merged.get("url", ""),
            "prompt": merged.get("prompt", ""),
        })
        r.raise_for_status()
    return r.json()
