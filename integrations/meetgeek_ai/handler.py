"""MeetGeek AI integration — AI meeting assistant."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.meetgeek.ai/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_token', '')}", "Content-Type": "application/json"}


@register_node("meetgeek_ai.get_meetings")
async def meetgeek_ai_get_meetings(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/meetings", params={"limit": merged.get("limit", 10)})
        r.raise_for_status()
    return {"meetings": r.json().get("data", [])}


@register_node("meetgeek_ai.get_transcript")
async def meetgeek_ai_get_transcript(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    meeting_id = merged.get("meeting_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/meetings/{meeting_id}/transcript")
        r.raise_for_status()
    return r.json()


@register_node("meetgeek_ai.get_summary")
async def meetgeek_ai_get_summary(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    meeting_id = merged.get("meeting_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/meetings/{meeting_id}/summary")
        r.raise_for_status()
    return r.json()
