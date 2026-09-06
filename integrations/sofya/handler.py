"""Sofya integration — AI-powered scheduling assistant."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.sofya.ai/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("sofya.schedule_meeting")
async def sofya_schedule_meeting(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/meetings", json={
            "participants": merged.get("participants", []),
            "duration": merged.get("duration", 30),
            "title": merged.get("title", "Meeting"),
        })
        r.raise_for_status()
    return r.json()


@register_node("sofya.get_availability")
async def sofya_get_availability(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/availability", params={"date_from": merged.get("date_from", ""), "date_to": merged.get("date_to", "")})
        r.raise_for_status()
    return r.json()
