"""
Currents.dev news API integration.

Provides access to latest news, search, and category listing via the
Currents API.

Credential fields:
  - api_key : Currents API key (passed as 'apiKey' query parameter)

Base URL: https://api.currentsapi.services/v1/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://api.currentsapi.services/v1"


async def _client(credential_id: str, db) -> tuple[httpx.AsyncClient, str]:
    """Returns (client, api_key) — api_key appended to each request as query param."""
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Currents credential missing 'api_key'")
    client = httpx.AsyncClient(
        base_url=_BASE_URL,
        timeout=30.0,
    )
    return client, api_key


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Currents API error {r.status_code}: {detail}")


@register_node("currents.get_latest_news")
async def currents_get_latest_news(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Get the latest news articles from Currents.dev.

    Config:
      - language   : ISO language code filter, e.g. 'en' (optional)
      - country    : ISO country code filter, e.g. 'US' (optional)
      - category   : Category filter (optional, see currents.get_available_categories)
      - page_size  : Number of articles per page (default 20, max 200)

    Returns:
      - news    : List of news article objects
      - status  : API response status
      - page    : Pagination cursor for next page (if available)
    """
    client, api_key = await _client(credential_id, db)

    params: dict = {"apiKey": api_key}
    language = config.get("language") or input_data.get("language")
    country = config.get("country") or input_data.get("country")
    category = config.get("category") or input_data.get("category")

    if language:
        params["language"] = language
    if country:
        params["country"] = country
    if category:
        params["category"] = category

    async with client:
        r = await client.get("/latest-news", params=params)
        _raise_for_status(r)
        data = r.json()

    return {
        "news": data.get("news", []),
        "status": data.get("status"),
        "page": data.get("page"),
        "count": len(data.get("news", [])),
    }


@register_node("currents.search_news")
async def currents_search_news(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Search news articles on Currents.dev.

    Config:
      - keywords   : Keywords to search for (required)
      - language   : ISO language code filter, e.g. 'en'
      - country    : ISO country code filter, e.g. 'US'
      - category   : Category to filter by
      - start_date : Filter articles after this date (ISO 8601, e.g. '2024-01-01 00:00:00 +0000')
      - end_date   : Filter articles before this date (ISO 8601)
      - page_number: Pagination (default: 1)

    Returns:
      - news   : List of matching news article objects
      - status : API response status
      - page   : Pagination token
    """
    keywords = config.get("keywords") or input_data.get("keywords")
    if not keywords:
        raise ValueError("currents.search_news requires 'keywords'")

    client, api_key = await _client(credential_id, db)

    params: dict = {"apiKey": api_key, "keywords": keywords}

    for key, param_key in [
        ("language", "language"),
        ("country", "country"),
        ("category", "category"),
        ("start_date", "start_date"),
        ("end_date", "end_date"),
        ("page_number", "page_number"),
    ]:
        val = config.get(key) or input_data.get(key)
        if val is not None:
            params[param_key] = val

    async with client:
        r = await client.get("/search", params=params)
        _raise_for_status(r)
        data = r.json()

    return {
        "news": data.get("news", []),
        "status": data.get("status"),
        "page": data.get("page"),
        "count": len(data.get("news", [])),
        "keywords": keywords,
    }


@register_node("currents.get_available_categories")
async def currents_get_available_categories(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve available news categories from Currents.dev.

    Returns:
      - categories : List of category strings
      - status     : API response status
    """
    client, api_key = await _client(credential_id, db)

    async with client:
        r = await client.get("/available/categories", params={"apiKey": api_key})
        _raise_for_status(r)
        data = r.json()

    categories = data.get("categories", data.get("data", []))
    return {
        "categories": categories,
        "count": len(categories),
        "status": data.get("status"),
    }


@register_node("currents.get_available_languages")
async def currents_get_available_languages(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve available languages supported by Currents.dev.

    Returns:
      - languages : Dict or list of supported languages
      - status    : API response status
    """
    client, api_key = await _client(credential_id, db)

    async with client:
        r = await client.get("/available/languages", params={"apiKey": api_key})
        _raise_for_status(r)
        data = r.json()

    languages = data.get("languages", data.get("data", []))
    return {
        "languages": languages,
        "count": len(languages) if isinstance(languages, list) else None,
        "status": data.get("status"),
    }


@register_node("currents.get_available_regions")
async def currents_get_available_regions(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve available regions/countries supported by Currents.dev.

    Returns:
      - regions : Dict or list of supported regions
      - status  : API response status
    """
    client, api_key = await _client(credential_id, db)

    async with client:
        r = await client.get("/available/regions", params={"apiKey": api_key})
        _raise_for_status(r)
        data = r.json()

    regions = data.get("regions", data.get("data", []))
    return {
        "regions": regions,
        "count": len(regions) if isinstance(regions, list) else None,
        "status": data.get("status"),
    }
