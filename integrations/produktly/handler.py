"""Produktly integration — product engagement and onboarding."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.produktly.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("produktly.track_event")
async def produktly_track_event(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/events", json={
            "event": merged.get("event", ""),
            "user_id": merged.get("user_id", ""),
            "properties": merged.get("properties", {}),
        })
        r.raise_for_status()
    return r.json()


@register_node("produktly.identify_user")
async def produktly_identify_user(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/users", json={
            "user_id": merged.get("user_id", ""),
            "traits": merged.get("traits", {}),
        })
        r.raise_for_status()
    return r.json()
