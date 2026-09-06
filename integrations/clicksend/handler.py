"""ClickSend integration for SMS, email, MMS messaging and account management."""
import base64
import httpx
import structlog

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://rest.clicksend.com/v3"


def _get_headers(username: str, api_key: str) -> dict:
    token = base64.b64encode(f"{username}:{api_key}".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
    }


@register_node("clicksend.send_sms")
async def clicksend_send_sms(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send one or more SMS messages via ClickSend."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    username = creds.get("username")
    api_key = creds.get("api_key")
    if not username or not api_key:
        raise ValueError("clicksend requires 'username' and 'api_key'")

    messages = merged.get("messages")
    if not messages:
        to = merged.get("to")
        body = merged.get("body") or merged.get("message")
        if not to or not body:
            raise ValueError("send_sms requires 'messages' list or 'to' and 'body'")
        messages = [{"to": to, "body": body, "from": merged.get("from", "")}]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}/sms/send",
            headers=_get_headers(username, api_key),
            json={"messages": messages},
        )
        r.raise_for_status()
        return r.json()


@register_node("clicksend.send_email")
async def clicksend_send_email(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a transactional email via ClickSend."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    username = creds.get("username")
    api_key = creds.get("api_key")
    to = merged.get("to")
    subject = merged.get("subject", "")
    body = merged.get("body") or merged.get("html_body", "")
    from_email = merged.get("from_email") or merged.get("from")
    from_name = merged.get("from_name", "")
    if not to or not subject:
        raise ValueError("send_email requires 'to' and 'subject'")

    recipients = to if isinstance(to, list) else [{"email": to}]
    payload = {
        "to": recipients,
        "from": {"email_address_id": merged.get("email_address_id", 0)},
        "subject": subject,
        "body": body,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}/email/send",
            headers=_get_headers(username, api_key),
            json=payload,
        )
        r.raise_for_status()
        return r.json()


@register_node("clicksend.send_mms")
async def clicksend_send_mms(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send MMS messages via ClickSend."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    username = creds.get("username")
    api_key = creds.get("api_key")
    to = merged.get("to")
    subject = merged.get("subject", "")
    media_file = merged.get("media_file")
    if not to or not media_file:
        raise ValueError("send_mms requires 'to' and 'media_file' URL")

    messages = [{"to": to, "subject": subject, "media_file": media_file, "from": merged.get("from", "")}]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}/mms/send",
            headers=_get_headers(username, api_key),
            json={"messages": messages},
        )
        r.raise_for_status()
        return r.json()


@register_node("clicksend.list_messages")
async def clicksend_list_messages(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List sent SMS messages with history."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    username = creds.get("username")
    api_key = creds.get("api_key")

    params = {"page": int(merged.get("page", 1)), "limit": int(merged.get("limit", 15))}
    if merged.get("date_from"):
        params["date_from"] = merged["date_from"]
    if merged.get("date_to"):
        params["date_to"] = merged["date_to"]
    if merged.get("q"):
        params["q"] = merged["q"]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{BASE_URL}/sms/history",
            headers=_get_headers(username, api_key),
            params=params,
        )
        r.raise_for_status()
        return r.json()


@register_node("clicksend.get_credits")
async def clicksend_get_credits(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get account credit balance."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    username = creds.get("username")
    api_key = creds.get("api_key")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{BASE_URL}/account",
            headers=_get_headers(username, api_key),
        )
        r.raise_for_status()
        data = r.json()
        return {"balance": data.get("data", {}).get("balance"), "account": data.get("data", {})}
