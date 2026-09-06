"""LiveSession session replay and analytics — handler for livesession integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.livesession.io/v1"


@register_node("livesession.list_sessions")
async def livesession_list_sessions(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List recorded sessions.

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
    log.info("livesession.list_sessions")
    return {"data": data}

@register_node("livesession.get_session")
async def livesession_get_session(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get session details.

    config/input_data:
      api_key — API key or token (required)
      session_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    session_id = merged.get("session_id") or ""
    if not session_id:
        raise ValueError("session_id required for livesession.get_session")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/sessions/{session_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("livesession.get_session")
    return {"data": data}
