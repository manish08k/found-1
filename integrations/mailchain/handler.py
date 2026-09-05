"""Mailchain integration — Web3 email via Mailchain API."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

MAILCHAIN_BASE = "https://api.mailchain.com"


def _headers(config: dict, input_data: dict) -> dict:
    merged = {**config, **input_data}
    return {"Authorization": f"Bearer {merged.get('api_key', '')}"}


@register_node("mailchain.send_message")
async def send_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a Web3 message via Mailchain.

    config/input_data:
      api_key   — Mailchain API key (required)
      from_addr — Sender address (required)
      to_addr   — Recipient address (required)
      subject   — Message subject (required)
      body      — Message body (required)
    """
    merged = {**config, **input_data}
    from_addr = merged.get("from_addr", "") or merged.get("from", "")
    to_addr = merged.get("to_addr", "") or merged.get("to", "")
    subject = merged.get("subject", "")
    body = merged.get("body", "")
    if not from_addr or not to_addr or not subject:
        raise ValueError("from_addr, to_addr, and subject are required for mailchain.send_message")
    headers = _headers(config, input_data)
    payload = {
        "from": from_addr,
        "to": [to_addr],
        "subject": subject,
        "content": {"text/plain": body},
    }
    async with httpx.AsyncClient(base_url=MAILCHAIN_BASE, timeout=30) as client:
        r = await client.post("/messages", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("mailchain.send_message", from_addr=from_addr, to_addr=to_addr, subject=subject)
    return {"result": data, "from_addr": from_addr, "to_addr": to_addr, "subject": subject}


@register_node("mailchain.list_messages")
async def list_messages(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List messages from a Mailchain address.

    config/input_data:
      api_key — Mailchain API key (required)
      address — Address to list messages for (required)
    """
    merged = {**config, **input_data}
    address = merged.get("address", "")
    if not address:
        raise ValueError("address is required for mailchain.list_messages")
    headers = _headers(config, input_data)
    async with httpx.AsyncClient(base_url=MAILCHAIN_BASE, timeout=30) as client:
        r = await client.get("/messages", params={"from": address}, headers=headers)
        r.raise_for_status()
        data = r.json()
    messages = data.get("messages", data) if isinstance(data, dict) else data
    log.info("mailchain.list_messages", address=address)
    return {"messages": messages, "address": address}
