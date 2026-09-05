"""
MSG91 SMS India integration.

Provides SMS sending, balance checking, OTP sending and verification via
the MSG91 API v5.

Credential fields:
  - authkey : MSG91 authentication key

Auth: authkey header on every request.
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://api.msg91.com/api/v5/"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    authkey = creds.get("authkey")
    if not authkey:
        raise ValueError("MSG91 credential missing 'authkey'")
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={
            "authkey": authkey,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"MSG91 API error {r.status_code}: {detail}")


@register_node("msg91.send_sms")
async def msg91_send_sms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Send an SMS message via MSG91."""
    mobiles = config.get("mobiles") or input_data.get("mobiles") or config.get("to") or input_data.get("to")
    message = config.get("message") or input_data.get("message")
    sender = config.get("sender") or input_data.get("sender")
    route = config.get("route") or input_data.get("route", "4")

    if not mobiles:
        raise ValueError("msg91.send_sms requires 'mobiles' (or 'to')")
    if not message:
        raise ValueError("msg91.send_sms requires 'message'")

    # Ensure mobiles is a string (comma-separated if list)
    if isinstance(mobiles, list):
        mobiles = ",".join(str(m) for m in mobiles)

    payload: dict = {
        "route": str(route),
        "sender": sender or "MSG91",
        "country": str(config.get("country") or input_data.get("country", "91")),
        "sms": [
            {
                "message": message,
                "to": [mobiles],
            }
        ],
    }

    log.info("msg91.send_sms", mobiles=mobiles, route=route)
    async with await _client(credential_id, db) as client:
        r = await client.post("flow/", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {
        "request_id": data.get("request_id"),
        "type": data.get("type"),
        "message": data.get("message"),
        "raw": data,
    }


@register_node("msg91.get_balance")
async def msg91_get_balance(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve the current MSG91 account SMS balance."""
    log.info("msg91.get_balance")
    async with await _client(credential_id, db) as client:
        r = await client.get("balance")
        _raise_for_status(r)
        data = r.json()

    return {
        "balance": data.get("balance"),
        "credits": data.get("credits"),
        "raw": data,
    }


@register_node("msg91.send_otp")
async def msg91_send_otp(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Send an OTP to a mobile number via MSG91."""
    mobile = config.get("mobile") or input_data.get("mobile") or config.get("to") or input_data.get("to")
    template_id = config.get("template_id") or input_data.get("template_id")

    if not mobile:
        raise ValueError("msg91.send_otp requires 'mobile'")

    otp_length = int(config.get("otp_length") or input_data.get("otp_length", 6))
    otp_expiry = int(config.get("otp_expiry") or input_data.get("otp_expiry", 5))
    sender = config.get("sender") or input_data.get("sender", "MSG91")

    params: dict = {
        "mobile": str(mobile),
        "otp_length": otp_length,
        "otp_expiry": otp_expiry,
        "sender": sender,
    }
    if template_id:
        params["template_id"] = template_id

    log.info("msg91.send_otp", mobile=mobile)
    async with await _client(credential_id, db) as client:
        r = await client.get("otp", params=params)
        _raise_for_status(r)
        data = r.json()

    return {
        "request_id": data.get("request_id"),
        "type": data.get("type"),
        "message": data.get("message"),
        "raw": data,
    }


@register_node("msg91.verify_otp")
async def msg91_verify_otp(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Verify an OTP submitted by a user."""
    mobile = config.get("mobile") or input_data.get("mobile")
    otp = config.get("otp") or input_data.get("otp")

    if not mobile:
        raise ValueError("msg91.verify_otp requires 'mobile'")
    if not otp:
        raise ValueError("msg91.verify_otp requires 'otp'")

    params = {
        "mobile": str(mobile),
        "otp": str(otp),
    }

    log.info("msg91.verify_otp", mobile=mobile)
    async with await _client(credential_id, db) as client:
        r = await client.get("otp/verify", params=params)
        _raise_for_status(r)
        data = r.json()

    verified = data.get("type") == "success"
    return {
        "verified": verified,
        "type": data.get("type"),
        "message": data.get("message"),
        "raw": data,
    }
