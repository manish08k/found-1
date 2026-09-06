"""Gamma integration — AI presentation creation."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.gamma.app/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("gamma.create_presentation")
async def gamma_create_presentation(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/generate", json={
            "title": merged.get("title", ""),
            "text": merged.get("text", ""),
            "theme": merged.get("theme", "default"),
        })
        r.raise_for_status()
    return r.json()


@register_node("gamma.get_presentation")
async def gamma_get_presentation(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    pres_id = merged.get("presentation_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/presentations/{pres_id}")
        r.raise_for_status()
    return r.json()
