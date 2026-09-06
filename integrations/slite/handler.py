"""Slite integration — team knowledge base and documentation."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.slite.com/v1"


def _headers(config: dict) -> dict:
    return {"x-slite-api-key": config.get("api_key", ""), "Content-Type": "application/json"}


@register_node("slite.create_note")
async def slite_create_note(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/notes", json={
            "title": merged.get("title", ""),
            "markdown": merged.get("content", ""),
            "channel_id": merged.get("channel_id", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("slite.search_notes")
async def slite_search_notes(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/notes/search", params={"query": merged.get("query", "")})
        r.raise_for_status()
    return {"notes": r.json()}


@register_node("slite.update_note")
async def slite_update_note(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    note_id = merged.get("note_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.patch(f"{BASE}/notes/{note_id}", json={
            "title": merged.get("title"),
            "markdown": merged.get("content"),
        })
        r.raise_for_status()
    return r.json()
