"""LogRocket session recording integration — sessions and issues."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

LOGROCKET_BASE = "https://api.logrocket.com/v1"


def _headers(config: dict, input_data: dict) -> dict:
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required")
    return {"Authorization": f"Bearer {api_key}"}


@register_node("logrocket.list_sessions")
async def logrocket_list_sessions(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List recent LogRocket sessions.

    config:
      api_key — LogRocket API key (required)
      limit   — maximum number of sessions to return (default 25)
    """
    headers = _headers(config, input_data)
    limit = int(config.get("limit", 25))

    async with httpx.AsyncClient(base_url=LOGROCKET_BASE, headers=headers, timeout=30) as client:
        r = await client.get("/sessions", params={"limit": limit})
        r.raise_for_status()
        data = r.json()

    sessions = data if isinstance(data, list) else data.get("sessions", [])
    log.info("logrocket.list_sessions", count=len(sessions))
    return {"sessions": sessions, "count": len(sessions)}


@register_node("logrocket.get_session")
async def logrocket_get_session(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single LogRocket session by ID.

    config/input_data:
      api_key — LogRocket API key (required)
      id      — session ID (required)
    """
    headers = _headers(config, input_data)
    session_id = config.get("id") or input_data.get("id")
    if not session_id:
        raise ValueError("id is required")

    async with httpx.AsyncClient(base_url=LOGROCKET_BASE, headers=headers, timeout=30) as client:
        r = await client.get(f"/sessions/{session_id}")
        r.raise_for_status()
        data = r.json()

    log.info("logrocket.get_session", session_id=session_id)
    return {"session": data, "id": session_id}


@register_node("logrocket.list_issues")
async def logrocket_list_issues(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List LogRocket issues.

    config:
      api_key — LogRocket API key (required)
      limit   — maximum number of issues to return (default 25)
    """
    headers = _headers(config, input_data)
    limit = int(config.get("limit", 25))

    async with httpx.AsyncClient(base_url=LOGROCKET_BASE, headers=headers, timeout=30) as client:
        r = await client.get("/issues", params={"limit": limit})
        r.raise_for_status()
        data = r.json()

    issues = data if isinstance(data, list) else data.get("issues", [])
    log.info("logrocket.list_issues", count=len(issues))
    return {"issues": issues, "count": len(issues)}
