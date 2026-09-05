"""
Marketstack stock market data integration.

Provides end-of-day data, ticker search, and intraday data
via the Marketstack API v1.

Credential fields:
  - api_key : Marketstack API key (sent as query parameter)

Auth: access_key query parameter.
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "http://api.marketstack.com/v1"


async def _get_api_key(credential_id: str, db) -> str:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Marketstack credential missing 'api_key'")
    return api_key


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Marketstack API error {r.status_code}: {detail}")


@register_node("marketstack.get_eod_data")
async def marketstack_get_eod_data(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Fetch end-of-day stock data for one or more symbols."""
    api_key = await _get_api_key(credential_id, db)

    symbols = config.get("symbols") or input_data.get("symbols")
    date_from = config.get("date_from") or input_data.get("date_from")
    date_to = config.get("date_to") or input_data.get("date_to")
    limit = int(config.get("limit") or input_data.get("limit", 100))
    offset = int(config.get("offset") or input_data.get("offset", 0))

    if not symbols:
        raise ValueError("marketstack.get_eod_data requires 'symbols'")

    # Accept list or comma-separated string
    if isinstance(symbols, list):
        symbols = ",".join(symbols)

    params: dict = {
        "access_key": api_key,
        "symbols": symbols,
        "limit": limit,
        "offset": offset,
    }
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to

    log.info("marketstack.get_eod_data", symbols=symbols)
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        r = await client.get("/eod", params=params)
        _raise_for_status(r)
        data = r.json()

    return {
        "data": data.get("data", []),
        "pagination": data.get("pagination", {}),
    }


@register_node("marketstack.search_tickers")
async def marketstack_search_tickers(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Search for stock tickers by keyword."""
    api_key = await _get_api_key(credential_id, db)

    search = config.get("search") or input_data.get("search")
    limit = int(config.get("limit") or input_data.get("limit", 25))
    offset = int(config.get("offset") or input_data.get("offset", 0))

    if not search:
        raise ValueError("marketstack.search_tickers requires 'search'")

    params: dict = {
        "access_key": api_key,
        "search": search,
        "limit": limit,
        "offset": offset,
    }

    log.info("marketstack.search_tickers", search=search)
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        r = await client.get("/tickers", params=params)
        _raise_for_status(r)
        data = r.json()

    return {
        "tickers": data.get("data", []),
        "pagination": data.get("pagination", {}),
    }


@register_node("marketstack.get_intraday_data")
async def marketstack_get_intraday_data(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Fetch intraday stock data for one or more symbols."""
    api_key = await _get_api_key(credential_id, db)

    symbols = config.get("symbols") or input_data.get("symbols")
    date_from = config.get("date_from") or input_data.get("date_from")
    date_to = config.get("date_to") or input_data.get("date_to")
    interval = config.get("interval") or input_data.get("interval", "1hour")
    limit = int(config.get("limit") or input_data.get("limit", 100))
    offset = int(config.get("offset") or input_data.get("offset", 0))

    if not symbols:
        raise ValueError("marketstack.get_intraday_data requires 'symbols'")

    if isinstance(symbols, list):
        symbols = ",".join(symbols)

    params: dict = {
        "access_key": api_key,
        "symbols": symbols,
        "interval": interval,
        "limit": limit,
        "offset": offset,
    }
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to

    log.info("marketstack.get_intraday_data", symbols=symbols, interval=interval)
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        r = await client.get("/intraday", params=params)
        _raise_for_status(r)
        data = r.json()

    return {
        "data": data.get("data", []),
        "pagination": data.get("pagination", {}),
    }
