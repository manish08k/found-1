"""
Plivo SMS and voice integration.

Credential fields:
  - auth_id: Plivo Auth ID
  - auth_token: Plivo Auth Token

Auth: HTTP Basic with auth_id:auth_token
Base URL: https://api.plivo.com/v1/Account/{auth_id}
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_PLIVO_BASE = "https://api.plivo.com/v1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    auth_id = creds.get("auth_id")
    auth_token = creds.get("auth_token")
    if not auth_id:
        raise ValueError("Plivo credential is missing 'auth_id'")
    if not auth_token:
        raise ValueError("Plivo credential is missing 'auth_token'")
    base_url = f"{_PLIVO_BASE}/Account/{auth_id}"
    return httpx.AsyncClient(
        base_url=base_url,
        auth=(auth_id, auth_token),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Plivo API error {r.status_code}: {detail}")
    if not r.content:
        return {}
    return r.json()


# ---------------------------------------------------------------------------
# SMS
# ---------------------------------------------------------------------------

@register_node("plivo.send_sms")
async def plivo_send_sms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /Message/ — send an SMS message."""
    src = config.get("src") if config.get("src") is not None else input_data.get("src")
    dst = config.get("dst") if config.get("dst") is not None else input_data.get("dst")
    text = config.get("text") if config.get("text") is not None else input_data.get("text")
    if not src or not dst or not text:
        raise ValueError("plivo.send_sms requires 'src', 'dst', and 'text'")
    body: dict = {"src": src, "dst": dst, "text": text}
    url = config.get("url") if config.get("url") is not None else input_data.get("url")
    if url is not None:
        body["url"] = url
    method = config.get("method") if config.get("method") is not None else input_data.get("method")
    if method is not None:
        body["method"] = method
    async with await _client(credential_id, db) as client:
        r = await client.post("/Message/", json=body)
    return _check(r)


@register_node("plivo.get_message")
async def plivo_get_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /Message/{message_uuid}/ — get details of an SMS message."""
    message_uuid = config.get("message_uuid") if config.get("message_uuid") is not None else input_data.get("message_uuid")
    if not message_uuid:
        raise ValueError("plivo.get_message requires 'message_uuid'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/Message/{message_uuid}/")
    return _check(r)


@register_node("plivo.list_messages")
async def plivo_list_messages(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /Message/ — list SMS messages."""
    params: dict = {}
    limit = config.get("limit") if config.get("limit") is not None else input_data.get("limit")
    if limit is not None:
        params["limit"] = int(limit)
    offset = config.get("offset") if config.get("offset") is not None else input_data.get("offset")
    if offset is not None:
        params["offset"] = int(offset)
    src = config.get("src") if config.get("src") is not None else input_data.get("src")
    if src is not None:
        params["src"] = src
    dst = config.get("dst") if config.get("dst") is not None else input_data.get("dst")
    if dst is not None:
        params["dst"] = dst
    message_direction = config.get("message_direction") if config.get("message_direction") is not None else input_data.get("message_direction")
    if message_direction is not None:
        params["message_direction"] = message_direction
    async with await _client(credential_id, db) as client:
        r = await client.get("/Message/", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Voice calls
# ---------------------------------------------------------------------------

@register_node("plivo.make_call")
async def plivo_make_call(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /Call/ — initiate an outbound call."""
    from_ = config.get("from") if config.get("from") is not None else input_data.get("from")
    to = config.get("to") if config.get("to") is not None else input_data.get("to")
    answer_url = config.get("answer_url") if config.get("answer_url") is not None else input_data.get("answer_url")
    if not from_ or not to or not answer_url:
        raise ValueError("plivo.make_call requires 'from', 'to', and 'answer_url'")
    body: dict = {"from": from_, "to": to, "answer_url": answer_url}
    answer_method = config.get("answer_method") if config.get("answer_method") is not None else input_data.get("answer_method")
    if answer_method is not None:
        body["answer_method"] = answer_method
    hangup_url = config.get("hangup_url") if config.get("hangup_url") is not None else input_data.get("hangup_url")
    if hangup_url is not None:
        body["hangup_url"] = hangup_url
    caller_name = config.get("caller_name") if config.get("caller_name") is not None else input_data.get("caller_name")
    if caller_name is not None:
        body["caller_name"] = caller_name
    async with await _client(credential_id, db) as client:
        r = await client.post("/Call/", json=body)
    return _check(r)


@register_node("plivo.get_call")
async def plivo_get_call(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /Call/{call_uuid}/ — get details of a specific call."""
    call_uuid = config.get("call_uuid") if config.get("call_uuid") is not None else input_data.get("call_uuid")
    if not call_uuid:
        raise ValueError("plivo.get_call requires 'call_uuid'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/Call/{call_uuid}/")
    return _check(r)


@register_node("plivo.list_calls")
async def plivo_list_calls(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /Call/ — list calls."""
    params: dict = {}
    limit = config.get("limit") if config.get("limit") is not None else input_data.get("limit")
    if limit is not None:
        params["limit"] = int(limit)
    offset = config.get("offset") if config.get("offset") is not None else input_data.get("offset")
    if offset is not None:
        params["offset"] = int(offset)
    call_direction = config.get("call_direction") if config.get("call_direction") is not None else input_data.get("call_direction")
    if call_direction is not None:
        params["call_direction"] = call_direction
    from_number = config.get("from_number") if config.get("from_number") is not None else input_data.get("from_number")
    if from_number is not None:
        params["from_number"] = from_number
    to_number = config.get("to_number") if config.get("to_number") is not None else input_data.get("to_number")
    if to_number is not None:
        params["to_number"] = to_number
    async with await _client(credential_id, db) as client:
        r = await client.get("/Call/", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Phone numbers & account
# ---------------------------------------------------------------------------

@register_node("plivo.list_phone_numbers")
async def plivo_list_phone_numbers(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /Number/ — list phone numbers on the account."""
    params: dict = {}
    limit = config.get("limit") if config.get("limit") is not None else input_data.get("limit")
    if limit is not None:
        params["limit"] = int(limit)
    offset = config.get("offset") if config.get("offset") is not None else input_data.get("offset")
    if offset is not None:
        params["offset"] = int(offset)
    number_type = config.get("number_type") if config.get("number_type") is not None else input_data.get("number_type")
    if number_type is not None:
        params["number_type"] = number_type
    async with await _client(credential_id, db) as client:
        r = await client.get("/Number/", params=params)
    return _check(r)


@register_node("plivo.get_account")
async def plivo_get_account(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET / — get account details."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/")
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(creds: dict) -> None:
    """Test Plivo credentials by fetching account info."""
    auth_id = creds.get("auth_id")
    auth_token = creds.get("auth_token")
    if not auth_id or not auth_token:
        raise ValueError("Missing 'auth_id' or 'auth_token'")
    base_url = f"{_PLIVO_BASE}/Account/{auth_id}"
    async with httpx.AsyncClient(
        base_url=base_url,
        auth=(auth_id, auth_token),
        headers={"Accept": "application/json"},
        timeout=15.0,
    ) as client:
        r = await client.get("/")
    if not r.is_success:
        raise ValueError(f"Plivo connection failed: {r.status_code} {r.text}")
