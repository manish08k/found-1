"""Cloutly integration — review management platform."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.cloutly.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("cloutly.send_review_request")
async def cloutly_send_review_request(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/review-requests", json={
            "name": merged.get("name", ""),
            "email": merged.get("email", ""),
            "location_id": merged.get("location_id", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("cloutly.get_reviews")
async def cloutly_get_reviews(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/reviews", params={"location_id": merged.get("location_id", "")})
        r.raise_for_status()
    return {"reviews": r.json()}
