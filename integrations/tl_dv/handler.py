"""tl;dv integration — AI-powered meeting recorder and summarizer."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.tldv.io/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("tl_dv.list_meetings")
async def tl_dv_list_meetings(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/meetings", params={
            "limit": merged.get("limit", 50),
            "offset": merged.get("offset", 0),
        })
        r.raise_for_status()
    return {"meetings": r.json()}


@register_node("tl_dv.get_meeting")
async def tl_dv_get_meeting(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    meeting_id = merged.get("meeting_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/meetings/{meeting_id}")
        r.raise_for_status()
    return r.json()


@register_node("tl_dv.get_transcript")
async def tl_dv_get_transcript(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    meeting_id = merged.get("meeting_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/meetings/{meeting_id}/transcript")
        r.raise_for_status()
    return r.json()


@register_node("tl_dv.get_highlights")
async def tl_dv_get_highlights(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    meeting_id = merged.get("meeting_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/meetings/{meeting_id}/highlights")
        r.raise_for_status()
    return {"highlights": r.json()}
