"""DataforB2B integration — B2B data enrichment."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.dataforb2b.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("dataforb2b.enrich_company")
async def dataforb2b_enrich_company(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/company/enrich", json={
            "domain": merged.get("domain", ""),
            "company_name": merged.get("company_name", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("dataforb2b.find_contacts")
async def dataforb2b_find_contacts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/contacts/search", json={
            "domain": merged.get("domain", ""),
            "title": merged.get("title", ""),
        })
        r.raise_for_status()
    return r.json()
