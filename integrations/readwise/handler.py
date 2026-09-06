"""Readwise integration — reading highlights and book summaries."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://readwise.io/api/v2"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Token {config.get('api_token', '')}", "Content-Type": "application/json"}


@register_node("readwise.get_highlights")
async def readwise_get_highlights(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/highlights/", params={"page_size": merged.get("limit", 20)})
        r.raise_for_status()
    data = r.json()
    return {"highlights": data.get("results", []), "count": data.get("count", 0)}


@register_node("readwise.create_highlights")
async def readwise_create_highlights(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    highlights = merged.get("highlights", [])
    if not isinstance(highlights, list):
        highlights = [highlights]
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/highlights/", json={"highlights": highlights})
        r.raise_for_status()
    return {"created": r.json()}


@register_node("readwise.get_books")
async def readwise_get_books(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/books/", params={"page_size": merged.get("limit", 20), "category": merged.get("category", "books")})
        r.raise_for_status()
    data = r.json()
    return {"books": data.get("results", []), "count": data.get("count", 0)}
