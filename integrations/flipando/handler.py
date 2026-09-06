"""Flipando integration — event ticketing and management."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.flipando.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("flipando.get_events")
async def flipando_get_events(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/events")
        r.raise_for_status()
    return {"events": r.json()}


@register_node("flipando.create_event")
async def flipando_create_event(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/events", json={
            "name": merged.get("name", ""),
            "date": merged.get("date", ""),
            "venue": merged.get("venue", ""),
        })
        r.raise_for_status()
    return r.json()
