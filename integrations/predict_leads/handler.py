"""Predict Leads integration — B2B lead scoring and prospecting."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://predictleads.com/api/v3"


def _headers(config: dict) -> dict:
    return {"X-Api-Key": config.get("api_key", ""), "Content-Type": "application/json"}


@register_node("predict_leads.find_companies")
async def predict_leads_find_companies(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/companies/search", json={
            "filters": merged.get("filters", {}),
            "limit": merged.get("limit", 20),
        })
        r.raise_for_status()
    return {"companies": r.json()}


@register_node("predict_leads.enrich_company")
async def predict_leads_enrich_company(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    domain = merged.get("domain", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/companies/{domain}")
        r.raise_for_status()
    return r.json()
