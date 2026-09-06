"""Azure Communication Services integration for SMS, email, and phone number management."""
import httpx
import structlog

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


def _get_headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


@register_node("azure_communication_services.send_sms")
async def acs_send_sms(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send an SMS message via Azure Communication Services."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    endpoint = creds.get("endpoint") or merged.get("endpoint")
    access_token = creds.get("access_token") or merged.get("access_token")
    if not endpoint or not access_token:
        raise ValueError("send_sms requires 'endpoint' and 'access_token'")

    from_number = merged.get("from_number") or merged.get("from")
    to_numbers = merged.get("to_numbers") or merged.get("to")
    message = merged.get("message")
    if not from_number or not to_numbers or not message:
        raise ValueError("send_sms requires 'from_number', 'to_numbers', and 'message'")
    if isinstance(to_numbers, str):
        to_numbers = [to_numbers]

    base_url = f"https://{endpoint}.communication.azure.com"
    payload = {
        "from": from_number,
        "smsRecipients": [{"to": n} for n in to_numbers],
        "message": message,
    }
    send_options = {}
    if merged.get("enable_delivery_report"):
        send_options["enableDeliveryReport"] = True
    if merged.get("tag"):
        send_options["tag"] = merged["tag"]
    if send_options:
        payload["smsSendOptions"] = send_options

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{base_url}/sms",
            headers=_get_headers(access_token),
            params={"api-version": "2021-03-07"},
            json=payload,
        )
        r.raise_for_status()
        return r.json()


@register_node("azure_communication_services.send_email")
async def acs_send_email(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send an email via Azure Communication Services Email."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    endpoint = creds.get("endpoint") or merged.get("endpoint")
    access_token = creds.get("access_token") or merged.get("access_token")
    if not endpoint or not access_token:
        raise ValueError("send_email requires 'endpoint' and 'access_token'")

    sender = merged.get("sender_address") or merged.get("from")
    to_addresses = merged.get("to_addresses") or merged.get("to", [])
    subject = merged.get("subject", "")
    html_body = merged.get("html_body") or merged.get("body", "")
    if isinstance(to_addresses, str):
        to_addresses = [to_addresses]

    base_url = f"https://{endpoint}.communication.azure.com"
    payload = {
        "senderAddress": sender,
        "recipients": {
            "to": [{"address": a} if isinstance(a, str) else a for a in to_addresses]
        },
        "content": {
            "subject": subject,
            "html": html_body,
        },
    }
    text_body = merged.get("text_body")
    if text_body:
        payload["content"]["plainText"] = text_body

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{base_url}/emails:send",
            headers=_get_headers(access_token),
            params={"api-version": "2023-03-31"},
            json=payload,
        )
        r.raise_for_status()
        return {"operation_id": r.headers.get("operation-location", ""), "status": "queued"}


@register_node("azure_communication_services.list_phone_numbers")
async def acs_list_phone_numbers(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List purchased phone numbers in the Azure Communication Services resource."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    endpoint = creds.get("endpoint") or merged.get("endpoint")
    access_token = creds.get("access_token") or merged.get("access_token")
    if not endpoint or not access_token:
        raise ValueError("list_phone_numbers requires 'endpoint' and 'access_token'")

    base_url = f"https://{endpoint}.communication.azure.com"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{base_url}/phoneNumbers",
            headers=_get_headers(access_token),
            params={"api-version": "2023-05-01"},
        )
        r.raise_for_status()
        data = r.json()
        return {"phone_numbers": data.get("phoneNumbers", []), "count": len(data.get("phoneNumbers", []))}
