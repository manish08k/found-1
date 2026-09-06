"""Lofty (Chime) integration — real estate CRM and marketing."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.chime.me/api/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("lofty.create_lead")
async def lofty_create_lead(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/leads", json={
            "name": merged.get("name", ""),
            "email": merged.get("email", ""),
            "phone": merged.get("phone", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("lofty.get_leads")
async def lofty_get_leads(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/leads", params={"per_page": merged.get("limit", 20)})
        r.raise_for_status()
    return {"leads": r.json()}
