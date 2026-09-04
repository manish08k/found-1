"""
RingCentral integration.

RingCentral REST API v1.0: https://developers.ringcentral.com/api-reference
Authentication: OAuth2 Bearer token

Credential fields (api-key type):
  - access_token: RingCentral OAuth2 access token
  - account_id:   Account ID (defaults to '~' for current account)

Supports: SMS, voice calls, call log, extensions, fax, meetings.
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

RC_BASE_URL = "https://platform.ringcentral.com/restapi/v1.0"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    access_token = creds.get("access_token")
    if not access_token:
        raise ValueError("RingCentral credential missing 'access_token'")
    return httpx.AsyncClient(
        base_url=RC_BASE_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _account(config: dict, input_data: dict) -> str:
    return config.get("account_id") or input_data.get("account_id") or "~"


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"RingCentral API error {r.status_code}: {detail}")
    if r.status_code == 204 or not r.content:
        return {}
    return r.json()


# ---------------------------------------------------------------------------
# SMS / Text Messages
# ---------------------------------------------------------------------------

@register_node("ringcentral.send_sms")
async def ringcentral_send_sms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /account/{id}/extension/{ext}/sms — send an SMS message."""
    account_id = _account(config, input_data)
    extension_id = config.get("extension_id") or input_data.get("extension_id") or "~"
    from_number = config.get("from") or input_data.get("from")
    to_numbers = config.get("to") or input_data.get("to")
    text = config.get("text") or input_data.get("text")
    if not from_number:
        raise ValueError("ringcentral.send_sms requires 'from' (E.164 phone number)")
    if not to_numbers:
        raise ValueError("ringcentral.send_sms requires 'to' (phone number or list)")
    if not text:
        raise ValueError("ringcentral.send_sms requires 'text'")
    if isinstance(to_numbers, str):
        to_numbers = [to_numbers]
    payload = {
        "from": {"phoneNumber": from_number},
        "to": [{"phoneNumber": n} for n in to_numbers],
        "text": text,
    }
    async with await _client(credential_id, db) as client:
        r = await client.post(
            f"/account/{account_id}/extension/{extension_id}/sms",
            json=payload,
        )
    return {"message": _check(r)}


@register_node("ringcentral.list_messages")
async def ringcentral_list_messages(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /account/{id}/extension/{ext}/message-store — list messages."""
    account_id = _account(config, input_data)
    extension_id = config.get("extension_id") or input_data.get("extension_id") or "~"
    params: dict = {}
    for key in ("dateFrom", "dateTo", "direction", "messageType", "perPage", "page"):
        val = config.get(key) or input_data.get(key)
        if val is not None:
            params[key] = val
    async with await _client(credential_id, db) as client:
        r = await client.get(
            f"/account/{account_id}/extension/{extension_id}/message-store",
            params=params,
        )
    return _check(r)


@register_node("ringcentral.get_message")
async def ringcentral_get_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /account/{id}/extension/{ext}/message-store/{msg_id}."""
    account_id = _account(config, input_data)
    extension_id = config.get("extension_id") or input_data.get("extension_id") or "~"
    message_id = config.get("message_id") or input_data.get("message_id")
    if not message_id:
        raise ValueError("ringcentral.get_message requires 'message_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(
            f"/account/{account_id}/extension/{extension_id}/message-store/{message_id}"
        )
    return {"message": _check(r)}


# ---------------------------------------------------------------------------
# Call Log
# ---------------------------------------------------------------------------

@register_node("ringcentral.get_call_log")
async def ringcentral_get_call_log(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /account/{id}/call-log — retrieve call log records."""
    account_id = _account(config, input_data)
    params: dict = {}
    for key in ("dateFrom", "dateTo", "direction", "type", "perPage", "page", "withRecording"):
        val = config.get(key) or input_data.get(key)
        if val is not None:
            params[key] = val
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/account/{account_id}/call-log", params=params)
    return _check(r)


@register_node("ringcentral.get_extension_call_log")
async def ringcentral_get_extension_call_log(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /account/{id}/extension/{ext}/call-log — extension-level call log."""
    account_id = _account(config, input_data)
    extension_id = config.get("extension_id") or input_data.get("extension_id") or "~"
    params: dict = {}
    for key in ("dateFrom", "dateTo", "direction", "type", "perPage", "page"):
        val = config.get(key) or input_data.get(key)
        if val is not None:
            params[key] = val
    async with await _client(credential_id, db) as client:
        r = await client.get(
            f"/account/{account_id}/extension/{extension_id}/call-log",
            params=params,
        )
    return _check(r)


# ---------------------------------------------------------------------------
# Extensions
# ---------------------------------------------------------------------------

@register_node("ringcentral.list_extensions")
async def ringcentral_list_extensions(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /account/{id}/extension — list all extensions."""
    account_id = _account(config, input_data)
    params: dict = {}
    for key in ("status", "type", "perPage", "page"):
        val = config.get(key) or input_data.get(key)
        if val is not None:
            params[key] = val
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/account/{account_id}/extension", params=params)
    return _check(r)


@register_node("ringcentral.get_extension")
async def ringcentral_get_extension(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /account/{id}/extension/{ext} — get extension details."""
    account_id = _account(config, input_data)
    extension_id = config.get("extension_id") or input_data.get("extension_id") or "~"
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/account/{account_id}/extension/{extension_id}")
    return {"extension": _check(r)}


# ---------------------------------------------------------------------------
# Ring Out (Outbound Calls)
# ---------------------------------------------------------------------------

@register_node("ringcentral.make_call")
async def ringcentral_make_call(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /account/{id}/extension/{ext}/ring-out — initiate a 2-leg call."""
    account_id = _account(config, input_data)
    extension_id = config.get("extension_id") or input_data.get("extension_id") or "~"
    from_number = config.get("from") or input_data.get("from")
    to_number = config.get("to") or input_data.get("to")
    if not from_number or not to_number:
        raise ValueError("ringcentral.make_call requires 'from' and 'to' phone numbers")
    payload = {
        "from": {"phoneNumber": from_number},
        "to": {"phoneNumber": to_number},
        "playPrompt": config.get("play_prompt", True),
    }
    async with await _client(credential_id, db) as client:
        r = await client.post(
            f"/account/{account_id}/extension/{extension_id}/ring-out",
            json=payload,
        )
    return {"call": _check(r)}


# ---------------------------------------------------------------------------
# Account Info
# ---------------------------------------------------------------------------

@register_node("ringcentral.get_account_info")
async def ringcentral_get_account_info(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /account/{id} — get account information."""
    account_id = _account(config, input_data)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/account/{account_id}")
    return {"account": _check(r)}


@register_node("ringcentral.get_service_info")
async def ringcentral_get_service_info(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /account/{id}/service-info — get service plan details."""
    account_id = _account(config, input_data)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/account/{account_id}/service-info")
    return {"service_info": _check(r)}


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(creds: dict) -> None:
    """Verify RingCentral credentials by fetching account info."""
    access_token = creds.get("access_token")
    if not access_token:
        raise ValueError("RingCentral requires 'access_token'")
    async with httpx.AsyncClient(
        base_url=RC_BASE_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15.0,
    ) as client:
        r = await client.get("/account/~")
    if not r.is_success:
        raise ValueError(f"RingCentral connection failed: {r.status_code} {r.text[:200]}")
