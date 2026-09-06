"""Sessions.us integration — virtual event and meeting platform."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.sessions.us/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("sessions_us.create_session")
async def sessions_us_create_session(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/sessions", json={
            "name": merged.get("name", ""),
            "start_time": merged.get("start_time", ""),
            "duration": merged.get("duration", 60),
        })
        r.raise_for_status()
    return r.json()


@register_node("sessions_us.get_sessions")
async def sessions_us_get_sessions(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/sessions", params={"limit": merged.get("limit", 10)})
        r.raise_for_status()
    return {"sessions": r.json()}
