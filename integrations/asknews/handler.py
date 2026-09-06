"""AskNews integration — AI-powered news search and summarization."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.asknews.app/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("asknews.search_news")
async def asknews_search_news(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/news/search", params={
            "q": merged.get("query", ""),
            "n_articles": merged.get("n_articles", 10),
            "return_type": merged.get("return_type", "both"),
        })
        r.raise_for_status()
    return r.json()


@register_node("asknews.get_story")
async def asknews_get_story(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    story_id = merged.get("story_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/stories/{story_id}")
        r.raise_for_status()
    return r.json()
