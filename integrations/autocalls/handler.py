"""Autocalls AI phone call automation — handler for autocalls integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.autocalls.ai/v1"


@register_node("autocalls.make_call")
async def autocalls_make_call(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Make an automated call.

    config/input_data:
      api_key — API key or token (required)
      phone_number — (required)
      script — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    phone_number = merged.get("phone_number") or ""
    script = merged.get("script") or ""
    if not phone_number or not script:
        raise ValueError("phone_number, script required for autocalls.make_call")
    payload = {"phone_number": phone_number, "script": script}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/calls", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("autocalls.make_call")
    return {"data": data}

@register_node("autocalls.list_calls")
async def autocalls_list_calls(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List calls.

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
    log.info("autocalls.list_calls")
    return {"data": data}

@register_node("autocalls.get_call")
async def autocalls_get_call(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get call details.

    config/input_data:
      api_key — API key or token (required)
      call_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    call_id = merged.get("call_id") or ""
    if not call_id:
        raise ValueError("call_id required for autocalls.get_call")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/calls/{call_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("autocalls.get_call")
    return {"data": data}
