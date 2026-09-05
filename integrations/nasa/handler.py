"""
NASA APIs integration.

Auth: api_key passed as query parameter.

Credential fields:
  - api_key: NASA API key (https://api.nasa.gov/)

Nodes:
  - nasa.get_apod          — Astronomy Picture of the Day
  - nasa.search_images     — NASA Image and Video Library search
  - nasa.get_neo           — Near Earth Objects feed
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://api.nasa.gov/"
_IMAGES_BASE = "https://images-api.nasa.gov"


async def _get_api_key(credential_id: str, db) -> str:
    if not credential_id:
        return "DEMO_KEY"
    creds = await get_credential_data(credential_id, db)
    return creds.get("api_key") or "DEMO_KEY"


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"NASA API error {r.status_code}: {detail}")
    if not r.content:
        return {}
    return r.json()


@register_node("nasa.get_apod")
async def get_apod(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    GET /planetary/apod — Astronomy Picture of the Day.

    Config (all optional):
      date       — YYYY-MM-DD (default: today)
      start_date — YYYY-MM-DD (range start)
      end_date   — YYYY-MM-DD (range end)
      count      — number of random images
      thumbs     — bool, return thumbnail URL for video
    """
    api_key = await _get_api_key(credential_id, db)
    params: dict = {"api_key": api_key}

    for field in ("date", "start_date", "end_date", "count", "thumbs"):
        val = config.get(field) if config.get(field) is not None else input_data.get(field)
        if val is not None:
            params[field] = val

    log.info("nasa.get_apod", params={k: v for k, v in params.items() if k != "api_key"})
    async with httpx.AsyncClient(base_url=_BASE_URL, timeout=30.0) as client:
        r = await client.get("/planetary/apod", params=params)
    return _check(r)


@register_node("nasa.search_images")
async def search_images(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    GET https://images-api.nasa.gov/search — NASA Image and Video Library.

    Config:
      q          — (required) free-text search query
      media_type — image | video | audio (optional)
      year_start — YYYY (optional)
      year_end   — YYYY (optional)
      page       — page number (optional)
    """
    query = config.get("q") or input_data.get("q") or config.get("query") or input_data.get("query")
    if not query:
        raise ValueError("nasa.search_images requires 'q' (search query)")

    params: dict = {"q": query}
    for field in ("media_type", "year_start", "year_end", "page"):
        val = config.get(field) if config.get(field) is not None else input_data.get(field)
        if val is not None:
            params[field] = val

    log.info("nasa.search_images", query=query)
    async with httpx.AsyncClient(base_url=_IMAGES_BASE, timeout=30.0) as client:
        r = await client.get("/search", params=params)
    return _check(r)


@register_node("nasa.get_neo")
async def get_neo(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    GET /neo/rest/v1/feed — Near Earth Objects feed.

    Config:
      start_date — YYYY-MM-DD (required)
      end_date   — YYYY-MM-DD (optional, default: start_date + 7 days)
    """
    api_key = await _get_api_key(credential_id, db)
    start_date = (
        config.get("start_date") or input_data.get("start_date")
    )
    end_date = config.get("end_date") or input_data.get("end_date")

    if not start_date:
        raise ValueError("nasa.get_neo requires 'start_date' (YYYY-MM-DD)")

    params: dict = {"api_key": api_key, "start_date": start_date}
    if end_date:
        params["end_date"] = end_date

    log.info("nasa.get_neo", start_date=start_date, end_date=end_date)
    async with httpx.AsyncClient(base_url=_BASE_URL, timeout=30.0) as client:
        r = await client.get("/neo/rest/v1/feed", params=params)
    return _check(r)


async def test_connection(creds: dict) -> None:
    """Verify NASA API key by fetching today's APOD."""
    api_key = creds.get("api_key") or "DEMO_KEY"
    async with httpx.AsyncClient(base_url=_BASE_URL, timeout=15.0) as client:
        r = await client.get("/planetary/apod", params={"api_key": api_key})
    if not r.is_success:
        raise ValueError(f"NASA connection failed: {r.status_code}")
