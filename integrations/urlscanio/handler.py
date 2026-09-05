"""urlscan.io integration — scan URLs, retrieve results, and search."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

URLSCAN_BASE = "https://urlscan.io/api/v1"


def _auth_headers(config: dict) -> dict:
    return {"API-Key": config.get("api_key", "")}


@register_node("urlscanio.scan_url")
async def urlscan_scan_url(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Submit a URL for scanning.

    config/input_data:
      api_key    — urlscan.io API key
      url        — URL to scan
      visibility — "public", "private", or "unlisted" (default "public")
    """
    merged = {**config, **input_data}
    url = merged.get("url")
    if not url:
        raise ValueError("url is required for urlscanio.scan_url")

    visibility = merged.get("visibility", "public")
    headers = {**_auth_headers(merged), "Content-Type": "application/json"}

    async with httpx.AsyncClient(base_url=URLSCAN_BASE, timeout=30) as client:
        r = await client.post(
            "/scan/",
            json={"url": url, "visibility": visibility},
            headers=headers,
        )
        r.raise_for_status()
        result = r.json()

    log.info("urlscanio.scan_url", url=url, uuid=result.get("uuid"))
    return {
        "uuid": result.get("uuid"),
        "result": result.get("result"),
        "api": result.get("api"),
        "visibility": result.get("visibility"),
        "url": result.get("url"),
        "message": result.get("message"),
    }


@register_node("urlscanio.get_result")
async def urlscan_get_result(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Retrieve the result of a previously submitted scan.

    config/input_data:
      api_key — urlscan.io API key
      uuid    — scan UUID returned by scan_url
    """
    merged = {**config, **input_data}
    uuid = merged.get("uuid")
    if not uuid:
        raise ValueError("uuid is required for urlscanio.get_result")

    headers = _auth_headers(merged)

    async with httpx.AsyncClient(base_url=URLSCAN_BASE, timeout=30) as client:
        r = await client.get(f"/result/{uuid}/", headers=headers)
        r.raise_for_status()
        result = r.json()

    log.info("urlscanio.get_result", uuid=uuid)
    return result


@register_node("urlscanio.search")
async def urlscan_search(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Search urlscan.io scan results.

    config/input_data:
      api_key — urlscan.io API key
      query   — Elasticsearch query string
      size    — number of results to return (default 10)
    """
    merged = {**config, **input_data}
    query = merged.get("query")
    if not query:
        raise ValueError("query is required for urlscanio.search")

    size = int(merged.get("size", 10))
    headers = _auth_headers(merged)

    async with httpx.AsyncClient(base_url=URLSCAN_BASE, timeout=30) as client:
        r = await client.get(
            "/search/",
            params={"q": query, "size": size},
            headers=headers,
        )
        r.raise_for_status()
        result = r.json()

    results = result.get("results", [])
    log.info("urlscanio.search", query=query, count=len(results))
    return {"results": results, "total": result.get("total", len(results))}
