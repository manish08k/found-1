"""Softr integration — no-code web app builder."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://studio-api.softr.io/v1"


def _headers(config: dict) -> dict:
    return {"Softr-Api-Key": config.get("api_key", ""), "Content-Type": "application/json"}


@register_node("softr.get_records")
async def softr_get_records(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    domain = merged.get("domain", "")
    app_id = merged.get("app_id", "")
    async with httpx.AsyncClient(headers={**_headers(merged), "Softr-Domain": domain}, timeout=30) as client:
        r = await client.get(f"{BASE}/applications/{app_id}/data-sources/{merged.get('data_source_id', '')}/records")
        r.raise_for_status()
    return {"records": r.json()}


@register_node("softr.create_user")
async def softr_create_user(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    app_id = merged.get("app_id", "")
    async with httpx.AsyncClient(headers={**_headers(merged), "Softr-Domain": merged.get("domain", "")}, timeout=30) as client:
        r = await client.post(f"{BASE}/applications/{app_id}/users", json={
            "email": merged.get("email", ""),
            "password": merged.get("password", ""),
        })
        r.raise_for_status()
    return r.json()
