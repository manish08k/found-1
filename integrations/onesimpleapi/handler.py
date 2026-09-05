"""
OneSimpleAPI integration.

Auth: api_key passed as a query parameter.

Credential fields:
  - api_key: OneSimpleAPI token (https://onesimpleapi.com/)

Nodes:
  - onesimpleapi.take_screenshot   — capture a webpage screenshot
  - onesimpleapi.generate_pdf      — convert a webpage to PDF
  - onesimpleapi.get_exchange_rate — retrieve live currency exchange rates
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://onesimpleapi.com/api/"


async def _get_api_key(credential_id: str, db) -> str:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("OneSimpleAPI credential missing 'api_key'")
    return api_key


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"OneSimpleAPI error {r.status_code}: {detail}")
    content_type = r.headers.get("content-type", "")
    if "application/json" in content_type:
        return r.json()
    # Binary responses (image/PDF) — return metadata
    return {
        "content_type": content_type,
        "size": len(r.content),
        "content": r.content,
    }


@register_node("onesimpleapi.take_screenshot")
async def take_screenshot(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    GET /screenshot — capture a screenshot of a webpage.

    Config:
      url     — (required) page URL to screenshot
      output  — png | jpg (default: png)
      width   — viewport width in pixels (default: 1280)
      height  — viewport height in pixels (optional)
      delay   — wait time in ms before capture (optional)
      full    — bool, capture full page (optional)
    """
    api_key = await _get_api_key(credential_id, db)
    url = config.get("url") or input_data.get("url")
    if not url:
        raise ValueError("onesimpleapi.take_screenshot requires 'url'")

    params: dict = {"token": api_key, "url": url}
    for field in ("output", "width", "height", "delay", "full"):
        val = config.get(field) if config.get(field) is not None else input_data.get(field)
        if val is not None:
            params[field] = val

    log.info("onesimpleapi.take_screenshot", url=url)
    async with httpx.AsyncClient(base_url=_BASE_URL, timeout=60.0) as client:
        r = await client.get("screenshot", params=params)
    return _check(r)


@register_node("onesimpleapi.generate_pdf")
async def generate_pdf(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    GET /pdf — convert a webpage to PDF.

    Config:
      url          — (required) page URL to convert
      format       — paper format: A4 | Letter | ... (default: A4)
      landscape    — bool, landscape orientation (optional)
      margin_top   — top margin (optional, e.g. "10mm")
      margin_bottom, margin_left, margin_right — margins (optional)
      print_background — bool, print CSS backgrounds (optional)
    """
    api_key = await _get_api_key(credential_id, db)
    url = config.get("url") or input_data.get("url")
    if not url:
        raise ValueError("onesimpleapi.generate_pdf requires 'url'")

    params: dict = {"token": api_key, "url": url}
    for field in ("format", "landscape", "margin_top", "margin_bottom",
                  "margin_left", "margin_right", "print_background"):
        val = config.get(field) if config.get(field) is not None else input_data.get(field)
        if val is not None:
            params[field] = val

    log.info("onesimpleapi.generate_pdf", url=url)
    async with httpx.AsyncClient(base_url=_BASE_URL, timeout=60.0) as client:
        r = await client.get("pdf", params=params)
    return _check(r)


@register_node("onesimpleapi.get_exchange_rate")
async def get_exchange_rate(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    GET /exchange-rate — retrieve live currency exchange rate.

    Config:
      from_currency — (required) source currency code (e.g. USD)
      to_currency   — (required) target currency code (e.g. EUR)
      amount        — (optional) amount to convert (default: 1)
    """
    api_key = await _get_api_key(credential_id, db)
    from_currency = (
        config.get("from_currency")
        or input_data.get("from_currency")
        or config.get("from")
        or input_data.get("from")
    )
    to_currency = (
        config.get("to_currency")
        or input_data.get("to_currency")
        or config.get("to")
        or input_data.get("to")
    )
    if not from_currency:
        raise ValueError("onesimpleapi.get_exchange_rate requires 'from_currency'")
    if not to_currency:
        raise ValueError("onesimpleapi.get_exchange_rate requires 'to_currency'")

    params: dict = {
        "token": api_key,
        "from": from_currency.upper(),
        "to": to_currency.upper(),
    }
    amount = config.get("amount") if config.get("amount") is not None else input_data.get("amount")
    if amount is not None:
        params["amount"] = amount

    log.info("onesimpleapi.get_exchange_rate", from_=from_currency, to=to_currency, amount=amount)
    async with httpx.AsyncClient(base_url=_BASE_URL, timeout=30.0) as client:
        r = await client.get("exchange-rate", params=params)
    return _check(r)


async def test_connection(creds: dict) -> None:
    """Verify OneSimpleAPI token with a minimal exchange rate request."""
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("OneSimpleAPI requires 'api_key'")
    async with httpx.AsyncClient(base_url=_BASE_URL, timeout=15.0) as client:
        r = await client.get("exchange-rate", params={"token": api_key, "from": "USD", "to": "EUR"})
    if not r.is_success:
        raise ValueError(f"OneSimpleAPI connection failed: {r.status_code}")
