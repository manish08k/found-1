"""Sendinblue (Brevo) integration — email and SMS marketing."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.sendinblue.com/v3"


def _headers(config: dict) -> dict:
    return {"api-key": config.get("api_key", ""), "Content-Type": "application/json"}


@register_node("sendinblue.send_email")
async def sendinblue_send_email(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/smtp/email", json={
            "sender": {"name": merged.get("from_name", ""), "email": merged.get("from_email", "")},
            "to": [{"email": merged.get("to", "")}],
            "subject": merged.get("subject", ""),
            "htmlContent": merged.get("html_content", ""),
            "textContent": merged.get("text_content", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("sendinblue.add_contact")
async def sendinblue_add_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/contacts", json={
            "email": merged.get("email", ""),
            "attributes": merged.get("attributes", {}),
            "listIds": merged.get("list_ids", []),
        })
        r.raise_for_status()
    return r.json()


@register_node("sendinblue.send_sms")
async def sendinblue_send_sms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/transactionalSMS/sms", json={
            "sender": merged.get("sender", ""),
            "recipient": merged.get("recipient", ""),
            "content": merged.get("content", ""),
        })
        r.raise_for_status()
    return r.json()
