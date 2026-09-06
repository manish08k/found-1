"""Devin integration — AI software engineering agent."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.cognition.ai/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("devin.create_session")
async def devin_create_session(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/sessions", json={
            "prompt": merged.get("prompt", ""),
            "snapshot_id": merged.get("snapshot_id"),
        })
        r.raise_for_status()
    return r.json()


@register_node("devin.get_session")
async def devin_get_session(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    session_id = merged.get("session_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/sessions/{session_id}")
        r.raise_for_status()
    return r.json()
