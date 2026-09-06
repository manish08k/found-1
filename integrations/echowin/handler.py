"""Echowin integration — AI phone agent."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.echo.win/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("echowin.make_call")
async def echowin_make_call(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/calls", json={
            "to": merged.get("to", ""),
            "agent_id": merged.get("agent_id", ""),
            "variables": merged.get("variables", {}),
        })
        r.raise_for_status()
    return r.json()


@register_node("echowin.get_call")
async def echowin_get_call(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    call_id = merged.get("call_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/calls/{call_id}")
        r.raise_for_status()
    return r.json()
