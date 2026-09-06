"""Google Search integration — web search via Custom Search API."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://www.googleapis.com/customsearch/v1"


@register_node("google_search.search")
async def google_search_search(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(BASE, params={
            "key": merged.get("api_key", ""),
            "cx": merged.get("search_engine_id", ""),
            "q": merged.get("query", ""),
            "num": merged.get("num", 10),
            "start": merged.get("start", 1),
        })
        r.raise_for_status()
    data = r.json()
    return {
        "results": [{"title": i["title"], "link": i["link"], "snippet": i.get("snippet", "")}
                    for i in data.get("items", [])],
        "total_results": data.get("searchInformation", {}).get("totalResults"),
    }
