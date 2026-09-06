"""Poper integration — website popup and lead capture."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://app.poper.ai/api/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("poper.get_leads")
async def poper_get_leads(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/leads", params={"limit": merged.get("limit", 50)})
        r.raise_for_status()
    return {"leads": r.json()}


@register_node("poper.get_campaigns")
async def poper_get_campaigns(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/campaigns")
        r.raise_for_status()
    return {"campaigns": r.json()}
