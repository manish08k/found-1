"""
Mocean SMS/Voice messaging integration.

Provides SMS sending, voice call initiation, and account balance queries
via the Mocean REST API v2.

Credential fields:
  - api_key    : Mocean API key
  - api_secret : Mocean API secret

Auth: api_key and api_secret passed as query parameters on every request.
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://rest.moceanapi.com/rest/2/"


async def _client(credential_id: str, db):
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    api_secret = creds.get("api_secret")
    if not api_key:
        raise ValueError("Mocean credential missing 'api_key'")
    if not api_secret:
        raise ValueError("Mocean credential missing 'api_secret'")
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        timeout=30.0,
    ), api_key, api_secret


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Mocean API error {r.status_code}: {detail}")


@register_node("mocean.send_sms")
async def mocean_send_sms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Send an SMS message via Mocean."""
    to = config.get("to") or input_data.get("to")
    from_ = config.get("from") or input_data.get("from")
    text = config.get("text") or input_data.get("text")

    if not to:
        raise ValueError("mocean.send_sms requires 'to'")
    if not from_:
        raise ValueError("mocean.send_sms requires 'from'")
    if not text:
        raise ValueError("mocean.send_sms requires 'text'")

    client, api_key, api_secret = await _client(credential_id, db)
    payload = {
        "mocean-api-key": api_key,
        "mocean-api-secret": api_secret,
        "mocean-to": to,
        "mocean-from": from_,
        "mocean-text": text,
        "mocean-resp-format": "json",
    }

    log.info("mocean.send_sms", to=to)
    async with client:
        r = await client.post("sms", data=payload)
        _raise_for_status(r)
        data = r.json()

    return {"result": data, "status": data.get("messages", [{}])[0].get("status", "unknown")}


@register_node("mocean.send_voice")
async def mocean_send_voice(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Initiate a voice call with a text-to-speech message via Mocean."""
    to = config.get("to") or input_data.get("to")
    from_ = config.get("from") or input_data.get("from")
    text = config.get("text") or input_data.get("text")

    if not to:
        raise ValueError("mocean.send_voice requires 'to'")
    if not from_:
        raise ValueError("mocean.send_voice requires 'from'")
    if not text:
        raise ValueError("mocean.send_voice requires 'text'")

    language = config.get("language") or input_data.get("language", "en-US")

    client, api_key, api_secret = await _client(credential_id, db)
    payload = {
        "mocean-api-key": api_key,
        "mocean-api-secret": api_secret,
        "mocean-to": to,
        "mocean-from": from_,
        "mocean-text": text,
        "mocean-language": language,
        "mocean-resp-format": "json",
    }

    log.info("mocean.send_voice", to=to)
    async with client:
        r = await client.post("voice/dial", data=payload)
        _raise_for_status(r)
        data = r.json()

    return {"result": data, "call_uuid": data.get("call_uuid")}


@register_node("mocean.get_account_balance")
async def mocean_get_account_balance(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve the current Mocean account balance."""
    client, api_key, api_secret = await _client(credential_id, db)
    params = {
        "mocean-api-key": api_key,
        "mocean-api-secret": api_secret,
        "mocean-resp-format": "json",
    }

    log.info("mocean.get_account_balance")
    async with client:
        r = await client.get("account/balance", params=params)
        _raise_for_status(r)
        data = r.json()

    return {"balance": data.get("value"), "currency": data.get("currency", ""), "raw": data}
