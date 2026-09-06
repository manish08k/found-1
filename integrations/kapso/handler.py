"""Kapso integration — AI-powered sales outreach."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.kapso.io/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("kapso.create_campaign")
async def kapso_create_campaign(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/campaigns", json={
            "name": merged.get("name", ""),
            "prospects": merged.get("prospects", []),
        })
        r.raise_for_status()
    return r.json()


@register_node("kapso.get_campaigns")
async def kapso_get_campaigns(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/campaigns")
        r.raise_for_status()
    return {"campaigns": r.json()}
