"""Exa neural search integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

EXA_BASE = "https://api.exa.ai"


@register_node("exa.search")
async def exa_search(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Search the web using Exa neural search.

    config/input_data:
      api_key    — Exa API key
      query      — search query
      num_results — number of results to return (default 10)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    query = merged.get("query") or ""
    num_results = int(merged.get("num_results", 10))

    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    payload = {"query": query, "numResults": num_results}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{EXA_BASE}/search", headers=headers, json=payload)
        r.raise_for_status()

    result = r.json()
    log.info("exa.search", query=query, result_count=len(result.get("results", [])))
    return {"result": result}


@register_node("exa.find_similar")
async def exa_find_similar(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Find similar pages to a given URL using Exa.

    config/input_data:
      api_key     — Exa API key
      url         — URL to find similar pages for
      num_results — number of results to return (default 10)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    url = merged.get("url") or ""
    num_results = int(merged.get("num_results", 10))

    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    payload = {"url": url, "numResults": num_results}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{EXA_BASE}/findSimilar", headers=headers, json=payload)
        r.raise_for_status()

    result = r.json()
    log.info("exa.find_similar", url=url, result_count=len(result.get("results", [])))
    return {"result": result}


@register_node("exa.get_contents")
async def exa_get_contents(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get full page contents for a list of Exa result IDs.

    config/input_data:
      api_key — Exa API key
      ids     — list of result IDs to fetch contents for
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    ids = merged.get("ids") or []

    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    payload = {"ids": ids}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{EXA_BASE}/contents", headers=headers, json=payload)
        r.raise_for_status()

    result = r.json()
    log.info("exa.get_contents", id_count=len(ids))
    return {"result": result}
