"""Brave Search API — handler for brave_search integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.search.brave.com/res/v1"


@register_node("brave_search.web_search")
async def brave_search_web_search(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Perform a web search.

    config/input_data:
      api_key — API key or token (required)
      q — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("subscription_token") or ""
    headers = {"X-Subscription-Token": api_key, "Content-Type": "application/json"}
    q = merged.get("q") or ""
    if not q:
        raise ValueError("q required for brave_search.web_search")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/web/search", headers=headers, params={"q": q})
        r.raise_for_status()
        data = r.json()
    log.info("brave_search.web_search")
    return {"data": data}

@register_node("brave_search.image_search")
async def brave_search_image_search(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Search for images.

    config/input_data:
      api_key — API key or token (required)
      q — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("subscription_token") or ""
    headers = {"X-Subscription-Token": api_key, "Content-Type": "application/json"}
    q = merged.get("q") or ""
    if not q:
        raise ValueError("q required for brave_search.image_search")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/images/search", headers=headers, params={"q": q})
        r.raise_for_status()
        data = r.json()
    log.info("brave_search.image_search")
    return {"data": data}

@register_node("brave_search.news_search")
async def brave_search_news_search(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Search news articles.

    config/input_data:
      api_key — API key or token (required)
      q — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("subscription_token") or ""
    headers = {"X-Subscription-Token": api_key, "Content-Type": "application/json"}
    q = merged.get("q") or ""
    if not q:
        raise ValueError("q required for brave_search.news_search")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/news/search", headers=headers, params={"q": q})
        r.raise_for_status()
        data = r.json()
    log.info("brave_search.news_search")
    return {"data": data}
