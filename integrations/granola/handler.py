"""Granola integration — AI meeting notes and summaries."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.granola.ai/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("granola.get_meetings")
async def granola_get_meetings(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/meetings", params={"limit": merged.get("limit", 10)})
        r.raise_for_status()
    return {"meetings": r.json()}


@register_node("granola.get_meeting_notes")
async def granola_get_meeting_notes(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    meeting_id = merged.get("meeting_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/meetings/{meeting_id}/notes")
        r.raise_for_status()
    return r.json()
