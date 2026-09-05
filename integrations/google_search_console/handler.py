"""Google Search Console integration — sites, search analytics, and sitemaps."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

GSC_BASE = "https://www.googleapis.com/webmasters/v3"


def _headers(config: dict, input_data: dict) -> dict:
    token = config.get("access_token") or input_data.get("access_token")
    if not token:
        raise ValueError("access_token is required")
    return {"Authorization": f"Bearer {token}"}


@register_node("google_search_console.list_sites")
async def gsc_list_sites(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all sites in Google Search Console.

    config:
      access_token — OAuth2 access token (required)
    """
    headers = _headers(config, input_data)

    async with httpx.AsyncClient(base_url=GSC_BASE, headers=headers, timeout=30) as client:
        r = await client.get("/sites")
        r.raise_for_status()
        data = r.json()

    sites = data.get("siteEntry", [])
    log.info("google_search_console.list_sites", count=len(sites))
    return {"sites": sites, "count": len(sites)}


@register_node("google_search_console.get_search_analytics")
async def gsc_get_search_analytics(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Query search analytics data for a site in Google Search Console.

    config/input_data:
      access_token — OAuth2 access token (required)
      site_url     — fully qualified site URL as registered in GSC (required)
      start_date   — start date YYYY-MM-DD (required)
      end_date     — end date YYYY-MM-DD (required)
      dimensions   — list of dimensions (default ['query'])
      row_limit    — max rows to return (default 25)
    """
    headers = _headers(config, input_data)
    site_url = config.get("site_url") or input_data.get("site_url")
    if not site_url:
        raise ValueError("site_url is required")
    start_date = config.get("start_date") or input_data.get("start_date")
    end_date = config.get("end_date") or input_data.get("end_date")
    if not start_date or not end_date:
        raise ValueError("start_date and end_date are required")
    dimensions = config.get("dimensions", ["query"])
    row_limit = int(config.get("row_limit", 25))

    payload = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": dimensions,
        "rowLimit": row_limit,
    }

    import urllib.parse
    encoded_site = urllib.parse.quote(site_url, safe="")

    async with httpx.AsyncClient(base_url=GSC_BASE, headers=headers, timeout=30) as client:
        r = await client.post(f"/sites/{encoded_site}/searchAnalytics/query", json=payload)
        r.raise_for_status()
        data = r.json()

    rows = data.get("rows", [])
    log.info("google_search_console.get_search_analytics", site_url=site_url, rows=len(rows))
    return {"rows": rows, "count": len(rows), "site_url": site_url}


@register_node("google_search_console.get_sitemaps")
async def gsc_get_sitemaps(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List sitemaps for a site in Google Search Console.

    config/input_data:
      access_token — OAuth2 access token (required)
      site_url     — fully qualified site URL as registered in GSC (required)
    """
    headers = _headers(config, input_data)
    site_url = config.get("site_url") or input_data.get("site_url")
    if not site_url:
        raise ValueError("site_url is required")

    import urllib.parse
    encoded_site = urllib.parse.quote(site_url, safe="")

    async with httpx.AsyncClient(base_url=GSC_BASE, headers=headers, timeout=30) as client:
        r = await client.get(f"/sites/{encoded_site}/sitemaps")
        r.raise_for_status()
        data = r.json()

    sitemaps = data.get("sitemap", [])
    log.info("google_search_console.get_sitemaps", site_url=site_url, count=len(sitemaps))
    return {"sitemaps": sitemaps, "count": len(sitemaps), "site_url": site_url}
