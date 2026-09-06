"""Housecall Pro integration — field service management."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.housecallpro.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Token token={config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("housecall_pro.get_jobs")
async def housecall_pro_get_jobs(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/jobs", params={"per_page": merged.get("limit", 20)})
        r.raise_for_status()
    return {"jobs": r.json().get("jobs", [])}


@register_node("housecall_pro.create_job")
async def housecall_pro_create_job(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/jobs", json={"job": {
            "customer_id": merged.get("customer_id", ""),
            "address_id": merged.get("address_id", ""),
            "description": merged.get("description", ""),
            "scheduled_start": merged.get("scheduled_start", ""),
        }})
        r.raise_for_status()
    return r.json()


@register_node("housecall_pro.get_customers")
async def housecall_pro_get_customers(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/customers", params={"per_page": merged.get("limit", 20)})
        r.raise_for_status()
    return {"customers": r.json().get("customers", [])}
