"""Lokalise integration — localization and translation management."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.lokalise.com/api2"


def _headers(config: dict) -> dict:
    return {"X-Api-Token": config.get("api_token", ""), "Content-Type": "application/json"}


@register_node("lokalise.get_keys")
async def lokalise_get_keys(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    project_id = merged.get("project_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/projects/{project_id}/keys", params={"limit": merged.get("limit", 100)})
        r.raise_for_status()
    return {"keys": r.json().get("keys", [])}


@register_node("lokalise.create_key")
async def lokalise_create_key(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    project_id = merged.get("project_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/projects/{project_id}/keys", json={
            "keys": [{"key_name": merged.get("key_name", ""), "translations": merged.get("translations", [])}]
        })
        r.raise_for_status()
    return r.json()


@register_node("lokalise.get_translations")
async def lokalise_get_translations(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    project_id = merged.get("project_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/projects/{project_id}/translations", params={"limit": merged.get("limit", 100), "lang_iso": merged.get("language", "en")})
        r.raise_for_status()
    return {"translations": r.json().get("translations", [])}
