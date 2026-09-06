"""Systeme.io integration — all-in-one online business platform."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.systeme.io/api"


def _headers(config: dict) -> dict:
    return {"X-API-Key": config.get("api_key", ""), "Content-Type": "application/json"}


@register_node("systeme_io.create_contact")
async def systeme_io_create_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/contacts", json={
            "email": merged.get("email", ""),
            "firstName": merged.get("first_name", ""),
            "lastName": merged.get("last_name", ""),
            "fields": merged.get("fields", []),
            "tags": merged.get("tags", []),
        })
        r.raise_for_status()
    return r.json()


@register_node("systeme_io.add_tag")
async def systeme_io_add_tag(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    contact_id = merged.get("contact_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/contacts/{contact_id}/tags", json={"tag": merged.get("tag", "")})
        r.raise_for_status()
    return r.json()


@register_node("systeme_io.get_contacts")
async def systeme_io_get_contacts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/contacts", params={"itemsPerPage": merged.get("limit", 20)})
        r.raise_for_status()
    return {"contacts": r.json().get("items", [])}
