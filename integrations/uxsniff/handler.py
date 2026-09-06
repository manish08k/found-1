"""UXSniff AI UX analytics — handler for uxsniff integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.uxsniff.com/v1"


@register_node("uxsniff.list_sessions")
async def uxsniff_list_sessions(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List user sessions.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/sessions", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("uxsniff.list_sessions")
    return {"data": data}

@register_node("uxsniff.get_session")
async def uxsniff_get_session(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get session replay.

    config/input_data:
      api_key — API key or token (required)
      session_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    session_id = merged.get("session_id") or ""
    if not session_id:
        raise ValueError("session_id required for uxsniff.get_session")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/sessions/{session_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("uxsniff.get_session")
    return {"data": data}

@register_node("uxsniff.get_insights")
async def uxsniff_get_insights(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get AI-generated UX insights.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/insights", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("uxsniff.get_insights")
    return {"data": data}
