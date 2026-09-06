"""Vapi voice AI platform — handler for vapi integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.vapi.ai"


@register_node("vapi.create_call")
async def vapi_create_call(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create an outbound call.

    config/input_data:
      api_key — API key or token (required)
      assistant_id — (required)
      customer — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    assistant_id = merged.get("assistant_id") or ""
    customer = merged.get("customer") or ""
    if not assistant_id or not customer:
        raise ValueError("assistant_id, customer required for vapi.create_call")
    payload = {"assistant_id": assistant_id, "customer": customer}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/call", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("vapi.create_call")
    return {"data": data}

@register_node("vapi.list_calls")
async def vapi_list_calls(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List calls.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/call", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("vapi.list_calls")
    return {"data": data}

@register_node("vapi.get_call")
async def vapi_get_call(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
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
        raise ValueError("call_id required for vapi.get_call")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/call/{call_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("vapi.get_call")
    return {"data": data}

@register_node("vapi.list_assistants")
async def vapi_list_assistants(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List assistants.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/assistant", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("vapi.list_assistants")
    return {"data": data}
