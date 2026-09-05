"""Tavily AI search integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

TAVILY_BASE = "https://api.tavily.com"


@register_node("tavily.search")
async def tavily_search(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Search the web using Tavily AI.

    config/input_data:
      api_key      — Tavily API key
      query        — search query
      search_depth — "basic" or "advanced" (default "basic")
      max_results  — maximum number of results (default 5)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    query = merged.get("query") or ""
    search_depth = merged.get("search_depth") or "basic"
    max_results = int(merged.get("max_results", 5))

    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": search_depth,
        "max_results": max_results,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{TAVILY_BASE}/search", json=payload)
        r.raise_for_status()

    result = r.json()
    log.info("tavily.search", query=query, result_count=len(result.get("results", [])))
    return {"result": result}


@register_node("tavily.extract")
async def tavily_extract(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Extract content from a URL using Tavily.

    config/input_data:
      api_key — Tavily API key
      url     — URL to extract content from
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    url = merged.get("url") or ""

    payload = {"api_key": api_key, "urls": [url]}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{TAVILY_BASE}/extract", json=payload)
        r.raise_for_status()

    result = r.json()
    log.info("tavily.extract", url=url)
    return {"result": result}
