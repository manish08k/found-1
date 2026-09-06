"""Salesloft integration — sales engagement platform."""
import httpx
import structlog
from core.execution_engine import register_node
from oauth.flow import get_access_token

log = structlog.get_logger(__name__)
BASE = "https://api.salesloft.com/v2"


async def _headers(credential_id: str, db) -> dict:
    token = await get_access_token(credential_id, db)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@register_node("salesloft.create_person")
async def salesloft_create_person(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.post(f"{BASE}/people.json", json={
            "email_address": merged.get("email", ""),
            "first_name": merged.get("first_name", ""),
            "last_name": merged.get("last_name", ""),
            "title": merged.get("title", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("salesloft.get_people")
async def salesloft_get_people(config: dict, input_data: dict, credential_id: str, db) -> dict:
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.get(f"{BASE}/people.json")
        r.raise_for_status()
    return {"people": r.json().get("data", [])}


@register_node("salesloft.create_cadence_membership")
async def salesloft_create_cadence_membership(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.post(f"{BASE}/cadence_memberships.json", json={
            "person_id": merged.get("person_id", ""),
            "cadence_id": merged.get("cadence_id", ""),
        })
        r.raise_for_status()
    return r.json()
