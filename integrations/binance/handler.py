"""Binance integration — cryptocurrency exchange data."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BINANCE_BASE = "https://api.binance.com/api/v3"


def _headers(api_key: str | None) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-MBX-APIKEY"] = api_key
    return headers


@register_node("binance.get_ticker_price")
async def binance_get_ticker_price(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get the latest price for a trading symbol.

    config:
      symbol  — Trading pair symbol e.g. "BTCUSDT" (required)
      api_key — Binance API key (optional for public endpoint)
    """
    symbol = config.get("symbol") or input_data.get("symbol", "BTCUSDT")
    api_key = config.get("api_key") or input_data.get("api_key")

    if not symbol:
        raise ValueError("symbol is required for binance.get_ticker_price")

    async with httpx.AsyncClient(base_url=BINANCE_BASE, timeout=30) as client:
        r = await client.get("/ticker/price", headers=_headers(api_key), params={"symbol": symbol})
        r.raise_for_status()
        data = r.json()

    log.info("binance.get_ticker_price", symbol=symbol, price=data.get("price"))
    return {"symbol": data.get("symbol"), "price": data.get("price"), "raw": data}


@register_node("binance.get_order_book")
async def binance_get_order_book(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get the order book (market depth) for a symbol.

    config:
      symbol  — Trading pair symbol e.g. "BTCUSDT" (required)
      limit   — Number of price levels (default 10, max 5000)
      api_key — Binance API key (optional)
    """
    symbol = config.get("symbol") or input_data.get("symbol", "BTCUSDT")
    limit = min(int(config.get("limit", 10)), 5000)
    api_key = config.get("api_key") or input_data.get("api_key")

    if not symbol:
        raise ValueError("symbol is required for binance.get_order_book")

    async with httpx.AsyncClient(base_url=BINANCE_BASE, timeout=30) as client:
        r = await client.get("/depth", headers=_headers(api_key), params={"symbol": symbol, "limit": limit})
        r.raise_for_status()
        data = r.json()

    log.info("binance.get_order_book", symbol=symbol, bids=len(data.get("bids", [])))
    return {"symbol": symbol, "bids": data.get("bids", []), "asks": data.get("asks", []), "last_update_id": data.get("lastUpdateId")}


@register_node("binance.get_account")
async def binance_get_account(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get Binance account information.

    Note: This endpoint requires API key and HMAC-SHA256 signature. This implementation
    sends the API key header but does NOT sign the request — you must provide a pre-signed
    timestamp+signature via config or use a signed proxy.

    config:
      api_key   — Binance API key (required)
      timestamp — Unix timestamp ms (required for signed requests)
      signature — HMAC-SHA256 signature (required for signed requests)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for binance.get_account")

    timestamp = config.get("timestamp") or input_data.get("timestamp")
    signature = config.get("signature") or input_data.get("signature")

    params: dict = {}
    if timestamp:
        params["timestamp"] = timestamp
    if signature:
        params["signature"] = signature

    async with httpx.AsyncClient(base_url=BINANCE_BASE, timeout=30) as client:
        r = await client.get("/account", headers=_headers(api_key), params=params)
        r.raise_for_status()
        data = r.json()

    balances = data.get("balances", [])
    non_zero = [b for b in balances if float(b.get("free", 0)) > 0 or float(b.get("locked", 0)) > 0]
    log.info("binance.get_account", account_type=data.get("accountType"), balance_count=len(non_zero))
    return {"account": data, "balances": non_zero, "account_type": data.get("accountType"), "can_trade": data.get("canTrade")}


@register_node("binance.get_recent_trades")
async def binance_get_recent_trades(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get recent trades for a symbol.

    config:
      symbol  — Trading pair symbol e.g. "BTCUSDT" (required)
      limit   — Number of trades (default 25, max 1000)
      api_key — Binance API key (optional)
    """
    symbol = config.get("symbol") or input_data.get("symbol", "BTCUSDT")
    limit = min(int(config.get("limit", 25)), 1000)
    api_key = config.get("api_key") or input_data.get("api_key")

    if not symbol:
        raise ValueError("symbol is required for binance.get_recent_trades")

    async with httpx.AsyncClient(base_url=BINANCE_BASE, timeout=30) as client:
        r = await client.get("/trades", headers=_headers(api_key), params={"symbol": symbol, "limit": limit})
        r.raise_for_status()
        trades = r.json()

    log.info("binance.get_recent_trades", symbol=symbol, count=len(trades))
    return {"trades": trades, "symbol": symbol, "count": len(trades)}
