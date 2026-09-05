"""
Brandfetch brand data and logo API integration.

Provides brand lookup by domain and brand search by name/keyword
via the Brandfetch API v2.

Credential fields:
  - api_key : Brandfetch API key (from brandfetch.com/developers).

Auth: Bearer token via Authorization header.
Base URL: https://api.brandfetch.io/v2/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.brandfetch.io/v2"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Brandfetch credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Brandfetch API error {r.status_code}: {detail}")


@register_node("brandfetch.get_brand")
async def bf_get_brand(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Retrieve full brand data for a domain, including logos, colors, fonts,
    company info, and social links.

    Params:
      - domain (required): The company domain to look up (e.g. 'stripe.com').
    """
    domain = config.get("domain") or input_data.get("domain")
    if not domain:
        raise ValueError("brandfetch.get_brand requires 'domain'")

    # Normalize — strip scheme if present
    domain = domain.removeprefix("https://").removeprefix("http://").rstrip("/")

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/brands/{domain}")
        _raise_for_status(r)
        data = r.json()

    log.info("brandfetch.get_brand", domain=domain, name=data.get("name"))
    return {
        "brand": data,
        "name": data.get("name"),
        "domain": data.get("domain"),
        "logos": data.get("logos", []),
        "colors": data.get("colors", []),
        "fonts": data.get("fonts", []),
        "company": data.get("company", {}),
        "links": data.get("links", []),
    }


@register_node("brandfetch.search_brands")
async def bf_search_brands(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Search for brands by company name or keyword.

    Params:
      - query (required): Search term (company name, keyword, etc.).
      - limit: Max number of results to return (default 10).
    """
    query = config.get("query") or input_data.get("query")
    if not query:
        raise ValueError("brandfetch.search_brands requires 'query'")

    limit = int(config.get("limit") or input_data.get("limit", 10))

    async with await _client(credential_id, db) as client:
        r = await client.get("/search", params={"query": query})
        _raise_for_status(r)
        data = r.json()

    results = data if isinstance(data, list) else data.get("results", [])
    results = results[:limit]

    log.info("brandfetch.search_brands", query=query, count=len(results))
    return {"brands": results, "count": len(results), "query": query}


@register_node("brandfetch.get_brand_logos")
async def bf_get_brand_logos(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Retrieve only logo assets for a domain (convenience wrapper).

    Params:
      - domain (required): The company domain (e.g. 'stripe.com').
      - format_filter: Filter logos by format — 'svg', 'png', 'jpeg'. Omit for all.
      - theme_filter: Filter logos by theme — 'light', 'dark'. Omit for all.
      - type_filter: Filter logos by type — 'logo', 'icon', 'symbol'. Omit for all.
    """
    domain = config.get("domain") or input_data.get("domain")
    if not domain:
        raise ValueError("brandfetch.get_brand_logos requires 'domain'")

    domain = domain.removeprefix("https://").removeprefix("http://").rstrip("/")

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/brands/{domain}")
        _raise_for_status(r)
        data = r.json()

    logos = data.get("logos", [])

    format_filter = config.get("format_filter") or input_data.get("format_filter")
    theme_filter = config.get("theme_filter") or input_data.get("theme_filter")
    type_filter = config.get("type_filter") or input_data.get("type_filter")

    # Flatten logo formats from nested structure
    flat_logos = []
    for logo_group in logos:
        logo_type = logo_group.get("type", "")
        if type_filter and logo_type != type_filter:
            continue
        for fmt in logo_group.get("formats", []):
            fmt_name = fmt.get("format", "")
            fmt_theme = fmt.get("background", "")  # Brandfetch uses 'background' for theme context
            if format_filter and fmt_name != format_filter:
                continue
            flat_logos.append({
                "type": logo_type,
                "format": fmt_name,
                "src": fmt.get("src"),
                "width": fmt.get("width"),
                "height": fmt.get("height"),
                "size": fmt.get("size"),
                "background": fmt_theme,
            })

    return {
        "logos": flat_logos,
        "count": len(flat_logos),
        "domain": domain,
        "brand_name": data.get("name"),
    }
