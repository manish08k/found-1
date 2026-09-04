"""
CoinGecko API integration.

Credential fields:
  - api_key: (optional) CoinGecko API key
             x-cg-demo-api-key header for free tier
             x-cg-pro-api-key header for Pro tier
  - pro: boolean — whether to use Pro API key header

Auth: Optional API key header
Base URL: https://api.coingecko.com/api/v3
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    is_pro = creds.get("pro", False)
    if isinstance(is_pro, str):
        is_pro = is_pro.lower() in ("true", "1", "yes")
    headers: dict = {"Content-Type": "application/json"}
    if api_key:
        if is_pro:
            headers["x-cg-pro-api-key"] = api_key
        else:
            headers["x-cg-demo-api-key"] = api_key
    return httpx.AsyncClient(
        base_url=COINGECKO_BASE_URL,
        headers=headers,
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"CoinGecko API error {r.status_code}: {detail}")
    try:
        return r.json()
    except Exception:
        return {"raw": r.text}


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@register_node("coingecko.get_price")
async def coingecko_get_price(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /simple/price — get current price for one or more coins."""
    ids = config.get("ids") or input_data.get("ids")
    vs_currencies = config.get("vs_currencies") or input_data.get("vs_currencies", "usd")
    if not ids:
        raise ValueError("coingecko.get_price requires 'ids'")
    ids_str = ",".join(ids) if isinstance(ids, list) else ids
    vs_str = ",".join(vs_currencies) if isinstance(vs_currencies, list) else vs_currencies
    params: dict = {"ids": ids_str, "vs_currencies": vs_str}
    include_market_cap = config.get("include_market_cap") or input_data.get("include_market_cap")
    if include_market_cap:
        params["include_market_cap"] = "true"
    include_24hr_change = config.get("include_24hr_change") or input_data.get("include_24hr_change")
    if include_24hr_change:
        params["include_24hr_change"] = "true"
    async with await _client(credential_id, db) as client:
        r = await client.get("/simple/price", params=params)
    return _check(r)


@register_node("coingecko.list_coins")
async def coingecko_list_coins(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /coins/list — list all coins with id, name, and symbol."""
    params: dict = {}
    include_platform = config.get("include_platform") or input_data.get("include_platform")
    if include_platform:
        params["include_platform"] = "true"
    async with await _client(credential_id, db) as client:
        r = await client.get("/coins/list", params=params)
    return _check(r)


@register_node("coingecko.get_coin")
async def coingecko_get_coin(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /coins/{id} — get full data for a specific coin."""
    coin_id = config.get("coin_id") or input_data.get("coin_id")
    if not coin_id:
        raise ValueError("coingecko.get_coin requires 'coin_id'")
    params: dict = {}
    localization = config.get("localization")
    if localization is False or input_data.get("localization") is False:
        params["localization"] = "false"
    tickers = config.get("tickers")
    if tickers is not None:
        params["tickers"] = "true" if tickers else "false"
    market_data = config.get("market_data")
    if market_data is not None:
        params["market_data"] = "true" if market_data else "false"
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/coins/{coin_id}", params=params)
    return _check(r)


@register_node("coingecko.get_coin_market_chart")
async def coingecko_get_coin_market_chart(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /coins/{id}/market_chart — get historical market data for a coin."""
    coin_id = config.get("coin_id") or input_data.get("coin_id")
    vs_currency = config.get("vs_currency") or input_data.get("vs_currency", "usd")
    days = config.get("days") or input_data.get("days", "7")
    if not coin_id:
        raise ValueError("coingecko.get_coin_market_chart requires 'coin_id'")
    params: dict = {"vs_currency": vs_currency, "days": str(days)}
    interval = config.get("interval") or input_data.get("interval")
    if interval:
        params["interval"] = interval
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/coins/{coin_id}/market_chart", params=params)
    return _check(r)


@register_node("coingecko.get_global")
async def coingecko_get_global(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /global — get global cryptocurrency market data."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/global")
    return _check(r)


@register_node("coingecko.list_markets")
async def coingecko_list_markets(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /coins/markets — list coins with market data."""
    vs_currency = config.get("vs_currency") or input_data.get("vs_currency", "usd")
    params: dict = {"vs_currency": vs_currency}
    ids = config.get("ids") or input_data.get("ids")
    if ids:
        params["ids"] = ",".join(ids) if isinstance(ids, list) else ids
    order = config.get("order") or input_data.get("order")
    if order:
        params["order"] = order
    per_page = config.get("per_page") or input_data.get("per_page")
    if per_page:
        params["per_page"] = min(int(per_page), 250)
    page = config.get("page") or input_data.get("page")
    if page:
        params["page"] = int(page)
    sparkline = config.get("sparkline") or input_data.get("sparkline")
    if sparkline:
        params["sparkline"] = "true"
    async with await _client(credential_id, db) as client:
        r = await client.get("/coins/markets", params=params)
    return _check(r)


@register_node("coingecko.search")
async def coingecko_search(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /search — search for coins, exchanges, and categories."""
    query = config.get("query") or input_data.get("query")
    if not query:
        raise ValueError("coingecko.search requires 'query'")
    async with await _client(credential_id, db) as client:
        r = await client.get("/search", params={"query": query})
    return _check(r)


@register_node("coingecko.trending")
async def coingecko_trending(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /search/trending — get trending coins and NFTs."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/search/trending")
    return _check(r)


@register_node("coingecko.list_categories")
async def coingecko_list_categories(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /coins/categories — list all coin categories."""
    params: dict = {}
    order = config.get("order") or input_data.get("order")
    if order:
        params["order"] = order
    async with await _client(credential_id, db) as client:
        r = await client.get("/coins/categories", params=params)
    return _check(r)


@register_node("coingecko.get_exchanges")
async def coingecko_get_exchanges(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /exchanges — list all exchanges with data."""
    params: dict = {}
    per_page = config.get("per_page") or input_data.get("per_page")
    if per_page:
        params["per_page"] = min(int(per_page), 250)
    page = config.get("page") or input_data.get("page")
    if page:
        params["page"] = int(page)
    async with await _client(credential_id, db) as client:
        r = await client.get("/exchanges", params=params)
    return _check(r)


async def test_connection(credential_id: str, db) -> dict:
    """Test CoinGecko connection by calling /ping."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/ping")
    _check(r)
    return {"ok": True}
