"""Pubrio integration — B2B prospecting and lead generation."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.pubrio.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("pubrio.search_companies")
async def pubrio_search_companies(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/companies/search", json=merged.get("filters", {}))
        r.raise_for_status()
    return {"companies": r.json()}


@register_node("pubrio.find_contacts")
async def pubrio_find_contacts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/contacts/search", json=merged.get("filters", {}))
        r.raise_for_status()
    return {"contacts": r.json()}
