"""Qwilr integration — beautiful proposals and quotes."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.qwilr.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("qwilr.create_page")
async def qwilr_create_page(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/pages", json={
            "template_id": merged.get("template_id", ""),
            "name": merged.get("name", ""),
            "variables": merged.get("variables", {}),
        })
        r.raise_for_status()
    return r.json()


@register_node("qwilr.get_page")
async def qwilr_get_page(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    page_id = merged.get("page_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/pages/{page_id}")
        r.raise_for_status()
    return r.json()


@register_node("qwilr.list_pages")
async def qwilr_list_pages(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/pages", params={"limit": merged.get("limit", 20)})
        r.raise_for_status()
    return {"pages": r.json()}
