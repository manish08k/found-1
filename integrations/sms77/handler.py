"""
sms77 SMS Germany integration.

Credential fields:
  - api_key: sms77 API key

Auth: X-Api-Key header.
Base URL: https://gateway.sms77.io/api/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://gateway.sms77.io/api/"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("sms77 credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={"X-Api-Key": api_key, "SentWith": "automation-platform"},
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> dict:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"sms77 API error {r.status_code}: {detail}")
    if not r.content:
        return {}
    try:
        return r.json()
    except Exception:
        return {"response": r.text}


@register_node("sms77.send_sms")
async def sms77_send_sms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Send an SMS message via sms77."""
    to = config.get("to") or input_data.get("to")
    text = config.get("text") or input_data.get("text")
    from_ = config.get("from") or input_data.get("from", "")
    flash = config.get("flash") or input_data.get("flash", 0)

    if not to:
        raise ValueError("sms77.send_sms requires 'to'")
    if not text:
        raise ValueError("sms77.send_sms requires 'text'")

    params: dict = {"to": to, "text": text, "json": 1}
    if from_:
        params["from"] = from_
    if flash:
        params["flash"] = flash

    log.info("sms77.send_sms", to=to)
    async with await _client(credential_id, db) as client:
        r = await client.post("sms", params=params)
    data = _raise_for_status(r)
    success = data.get("success") == "100" if isinstance(data, dict) else False
    return {"success": success, "response": data, "to": to}


@register_node("sms77.get_balance")
async def sms77_get_balance(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve the current account balance from sms77."""
    log.info("sms77.get_balance")
    async with await _client(credential_id, db) as client:
        r = await client.get("balance")
    if r.status_code >= 300:
        raise ValueError(f"sms77 API error {r.status_code}: {r.text}")
    try:
        balance = float(r.text.strip())
    except ValueError:
        balance = r.text.strip()
    return {"balance": balance}


@register_node("sms77.lookup_number")
async def sms77_lookup_number(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Look up information about a phone number via sms77."""
    number = config.get("number") or input_data.get("number")
    lookup_type = config.get("type") or input_data.get("type", "format")

    if not number:
        raise ValueError("sms77.lookup_number requires 'number'")

    valid_types = {"format", "hlr", "mnp", "cnam"}
    if lookup_type not in valid_types:
        raise ValueError(f"sms77.lookup_number: 'type' must be one of {sorted(valid_types)}")

    params = {"number": number, "type": lookup_type, "json": 1}

    log.info("sms77.lookup_number", number=number, lookup_type=lookup_type)
    async with await _client(credential_id, db) as client:
        r = await client.post("lookup", params=params)
    data = _raise_for_status(r)
    return {"lookup": data, "number": number, "type": lookup_type}
