"""Slashed integration — link shortening and analytics."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://slashed.pro/api/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("slashed.shorten_url")
async def slashed_shorten_url(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/links", json={
            "url": merged.get("url", ""),
            "custom_slug": merged.get("custom_slug"),
        })
        r.raise_for_status()
    return r.json()


@register_node("slashed.get_link_stats")
async def slashed_get_link_stats(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    link_id = merged.get("link_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/links/{link_id}/stats")
        r.raise_for_status()
    return r.json()
