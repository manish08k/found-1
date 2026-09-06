"""Leexi call recording and AI analysis — handler for leexi integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.leexi.ai/v1"


@register_node("leexi.list_calls")
async def leexi_list_calls(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List recorded calls.

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
    log.info("leexi.list_calls")
    return {"data": data}

@register_node("leexi.get_call")
async def leexi_get_call(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get call details and transcript.

    config/input_data:
      api_key — API key or token (required)
      call_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    call_id = merged.get("call_id") or ""
    if not call_id:
        raise ValueError("call_id required for leexi.get_call")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/calls/{call_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("leexi.get_call")
    return {"data": data}

@register_node("leexi.get_summary")
async def leexi_get_summary(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get call AI summary.

    config/input_data:
      api_key — API key or token (required)
      call_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    call_id = merged.get("call_id") or ""
    if not call_id:
        raise ValueError("call_id required for leexi.get_summary")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/calls/{call_id}/summary", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("leexi.get_summary")
    return {"data": data}
