"""Sperse integration — membership and subscription management."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.sperse.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("sperse.create_member")
async def sperse_create_member(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/members", json={
            "email": merged.get("email", ""),
            "name": merged.get("name", ""),
            "plan_id": merged.get("plan_id", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("sperse.get_members")
async def sperse_get_members(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/members", params={"limit": merged.get("limit", 20)})
        r.raise_for_status()
    return {"members": r.json()}
