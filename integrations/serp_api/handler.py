"""SerpAPI integration — Google, Bing, YouTube search results."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

SERPAPI_BASE = "https://serpapi.com"


@register_node("serp_api.search_google")
async def serp_api_search_google(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Search Google via SerpAPI.

    config:
      api_key    — SerpAPI key (required)
      query      — search query (required)
      location   — location e.g. "Austin, Texas" (optional)
      hl         — language code e.g. "en" (optional)
      gl         — country code e.g. "us" (optional)
      num        — number of results (optional, default 10)
      start      — result offset for pagination (optional, default 0)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    query = merged.get("query")
    if not api_key or not query:
        raise ValueError("api_key and query are required for serp_api.search_google")

    params: dict = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "num": merged.get("num", 10),
        "start": merged.get("start", 0),
    }
    for field in ["location", "hl", "gl"]:
        if merged.get(field):
            params[field] = merged[field]

    async with httpx.AsyncClient(base_url=SERPAPI_BASE, timeout=30) as client:
        r = await client.get("/search.json", params=params)
        r.raise_for_status()
        data = r.json()

    results = data.get("organic_results", [])
    log.info("serp_api.search_google", query=query, count=len(results))
    return {
        "organic_results": results,
        "count": len(results),
        "search_metadata": data.get("search_metadata"),
        "search_information": data.get("search_information"),
    }


@register_node("serp_api.search_bing")
async def serp_api_search_bing(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Search Bing via SerpAPI.

    config:
      api_key — SerpAPI key (required)
      query   — search query (required)
      cc      — country code e.g. "US" (optional)
      mkt     — market code e.g. "en-US" (optional)
      count   — number of results (optional, default 10)
      first   — result offset (optional, default 1)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    query = merged.get("query")
    if not api_key or not query:
        raise ValueError("api_key and query are required for serp_api.search_bing")

    params: dict = {
        "engine": "bing",
        "q": query,
        "api_key": api_key,
        "count": merged.get("count", 10),
        "first": merged.get("first", 1),
    }
    for field in ["cc", "mkt"]:
        if merged.get(field):
            params[field] = merged[field]

    async with httpx.AsyncClient(base_url=SERPAPI_BASE, timeout=30) as client:
        r = await client.get("/search.json", params=params)
        r.raise_for_status()
        data = r.json()

    results = data.get("organic_results", [])
    log.info("serp_api.search_bing", query=query, count=len(results))
    return {"organic_results": results, "count": len(results), "search_metadata": data.get("search_metadata")}


@register_node("serp_api.search_youtube")
async def serp_api_search_youtube(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Search YouTube via SerpAPI.

    config:
      api_key — SerpAPI key (required)
      query   — search query (required)
      hl      — language code (optional)
      gl      — country code (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    query = merged.get("query")
    if not api_key or not query:
        raise ValueError("api_key and query are required for serp_api.search_youtube")

    params: dict = {
        "engine": "youtube",
        "search_query": query,
        "api_key": api_key,
    }
    for field in ["hl", "gl"]:
        if merged.get(field):
            params[field] = merged[field]

    async with httpx.AsyncClient(base_url=SERPAPI_BASE, timeout=30) as client:
        r = await client.get("/search.json", params=params)
        r.raise_for_status()
        data = r.json()

    results = data.get("video_results", [])
    log.info("serp_api.search_youtube", query=query, count=len(results))
    return {"video_results": results, "count": len(results), "search_metadata": data.get("search_metadata")}


@register_node("serp_api.get_results")
async def serp_api_get_results(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Execute a generic SerpAPI search with full parameter control.

    config:
      api_key — SerpAPI key (required)
      engine  — search engine e.g. "google", "bing", "youtube" (required)
      params  — dict of additional SerpAPI parameters (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    engine = merged.get("engine", "google")
    extra_params = merged.get("params", {})
    if not api_key:
        raise ValueError("api_key is required for serp_api.get_results")

    params: dict = {"engine": engine, "api_key": api_key, **extra_params}

    async with httpx.AsyncClient(base_url=SERPAPI_BASE, timeout=30) as client:
        r = await client.get("/search.json", params=params)
        r.raise_for_status()
        data = r.json()

    log.info("serp_api.get_results", engine=engine)
    return {"data": data, "engine": engine, "search_metadata": data.get("search_metadata")}
