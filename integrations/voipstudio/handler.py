"""VoIPstudio cloud phone system — handler for voipstudio integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://l7api.com/v2.1"


@register_node("voipstudio.list_extensions")
async def voipstudio_list_extensions(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List extensions.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/extensions", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("voipstudio.list_extensions")
    return {"data": data}

@register_node("voipstudio.make_call")
async def voipstudio_make_call(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Make a call.

    config/input_data:
      api_key — API key or token (required)
      from_extension — (required)
      to — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    from_extension = merged.get("from_extension") or ""
    to = merged.get("to") or ""
    if not from_extension or not to:
        raise ValueError("from_extension, to required for voipstudio.make_call")
    payload = {"from_extension": from_extension, "to": to}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/calls", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("voipstudio.make_call")
    return {"data": data}

@register_node("voipstudio.list_calls")
async def voipstudio_list_calls(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
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
    log.info("voipstudio.list_calls")
    return {"data": data}
