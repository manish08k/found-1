"""KrispCall cloud phone system — handler for krisp_call integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.krispcall.com/v1"


@register_node("krisp_call.make_call")
async def krisp_call_make_call(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Make a phone call.

    config/input_data:
      api_key — API key or token (required)
      to — (required)
      from_number — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    to = merged.get("to") or ""
    from_number = merged.get("from_number") or ""
    if not to or not from_number:
        raise ValueError("to, from_number required for krisp_call.make_call")
    payload = {"to": to, "from_number": from_number}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/calls", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("krisp_call.make_call")
    return {"data": data}

@register_node("krisp_call.send_sms")
async def krisp_call_send_sms(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send an SMS.

    config/input_data:
      api_key — API key or token (required)
      to — (required)
      from_number — (required)
      body — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    to = merged.get("to") or ""
    from_number = merged.get("from_number") or ""
    body = merged.get("body") or ""
    if not to or not from_number or not body:
        raise ValueError("to, from_number, body required for krisp_call.send_sms")
    payload = {"to": to, "from_number": from_number, "body": body}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/sms", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("krisp_call.send_sms")
    return {"data": data}

@register_node("krisp_call.list_calls")
async def krisp_call_list_calls(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List call history.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/calls", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("krisp_call.list_calls")
    return {"data": data}
