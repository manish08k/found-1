"""Magical API integration — spreadsheet automation."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.magical.so/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("magical_api.get_templates")
async def magical_api_get_templates(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/templates")
        r.raise_for_status()
    return {"templates": r.json()}


@register_node("magical_api.use_template")
async def magical_api_use_template(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    template_id = merged.get("template_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/templates/{template_id}/use", json={"variables": merged.get("variables", {})})
        r.raise_for_status()
    return r.json()
