"""Fountain integration — high-volume hiring platform."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.fountain.com/v2"


def _headers(config: dict) -> dict:
    return {"X-FOUNTAIN-KEY": config.get("api_key", ""), "Content-Type": "application/json"}


@register_node("fountain.get_applicants")
async def fountain_get_applicants(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/applicants", params={"per_page": merged.get("limit", 20)})
        r.raise_for_status()
    return r.json()


@register_node("fountain.move_applicant")
async def fountain_move_applicant(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    applicant_id = merged.get("applicant_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/applicants/{applicant_id}/transitions", json={
            "stage_id": merged.get("stage_id", ""),
        })
        r.raise_for_status()
    return r.json()
