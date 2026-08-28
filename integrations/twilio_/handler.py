"""
Twilio integration — SMS. Credential fields:
{"account_sid": "AC...", "auth_token": "..."} — Twilio's REST API uses
HTTP Basic auth with these two values directly, no separate token
exchange needed.
"""
import re
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

TWILIO_BASE = "https://api.twilio.com/2010-04-01"

_E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")


def _validate_phone(number: str, field_name: str) -> None:
    if not number or not _E164_RE.match(number):
        raise ValueError(f"twilio.send_sms: '{field_name}' must be E.164 format (e.g. +14155552671)")


async def _client(credential_id: str, db) -> tuple[httpx.AsyncClient, str]:
    creds = await get_credential_data(credential_id, db)
    account_sid = creds.get("account_sid")
    auth_token = creds.get("auth_token")
    if not account_sid or not auth_token:
        raise ValueError("Twilio credential is missing 'account_sid' or 'auth_token'")
    client = httpx.AsyncClient(base_url=TWILIO_BASE, auth=(account_sid, auth_token), timeout=30)
    return client, account_sid


@register_node("twilio.send_sms")
async def twilio_send_sms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    to = config.get("to") or input_data.get("to")
    from_number = config.get("from") or input_data.get("from")
    body = config.get("body") or input_data.get("body", "")

    _validate_phone(to, "to")
    _validate_phone(from_number, "from")
    if not body:
        raise ValueError("twilio.send_sms requires 'body'")
    if len(body) > 1600:
        raise ValueError("twilio.send_sms: body exceeds 1600 characters (Twilio's concatenated-SMS limit)")

    client, account_sid = await _client(credential_id, db)
    async with client:
        r = await client.post(f"/Accounts/{account_sid}/Messages.json", data={
            "To": to, "From": from_number, "Body": body,
        })
        r.raise_for_status()
        data = r.json()

    return {"sid": data["sid"], "status": data["status"]}


async def test_connection(creds: dict) -> None:
    account_sid = creds.get("account_sid")
    auth_token = creds.get("auth_token")
    if not account_sid or not auth_token:
        raise ValueError("Missing account_sid or auth_token")
    async with httpx.AsyncClient(base_url=TWILIO_BASE, auth=(account_sid, auth_token), timeout=10) as client:
        r = await client.get(f"/Accounts/{account_sid}.json")
        r.raise_for_status()
