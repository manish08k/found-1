"""OpenPhone business phone system — handler for open_phone integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.openphone.com/v1"


@register_node("open_phone.send_message")
async def open_phone_send_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a text message via OpenPhone.

    config/input_data:
      api_key      -- OpenPhone API key (required)
      from_number  -- Sender phone number (required)
      to           -- Recipient phone number (required)
      content      -- Message content (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    from_number = merged.get("from_number") or merged.get("from") or ""
    to = merged.get("to") or ""
    content = merged.get("content") or ""
    if not from_number or not to or not content:
        raise ValueError("from_number, to, content required for open_phone.send_message")
    payload = {"from": from_number, "to": to, "content": content}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/messages", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("open_phone.send_message")
    return {"data": data}


@register_node("open_phone.list_phone_numbers")
async def open_phone_list_phone_numbers(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List phone numbers.

    config/input_data:
      api_key -- OpenPhone API key (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/phone-numbers", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("open_phone.list_phone_numbers")
    return {"data": data}


@register_node("open_phone.list_calls")
async def open_phone_list_calls(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List call history.

    config/input_data:
      api_key -- OpenPhone API key (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/calls", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("open_phone.list_calls")
    return {"data": data}


@register_node("open_phone.list_messages")
async def open_phone_list_messages(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List messages.

    config/input_data:
      api_key -- OpenPhone API key (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/messages", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("open_phone.list_messages")
    return {"data": data}
