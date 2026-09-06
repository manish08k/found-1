"""DatoCMS integration — headless CMS."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://site-api.datocms.com"


def _headers(config: dict) -> dict:
    return {
        "Authorization": f"Bearer {config.get('api_token', '')}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Api-Version": "3",
    }


@register_node("datocms.get_item")
async def datocms_get_item(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    item_id = merged.get("item_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/items/{item_id}")
        r.raise_for_status()
    return r.json()


@register_node("datocms.create_item")
async def datocms_create_item(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/items", json={
            "data": {
                "type": "item",
                "attributes": merged.get("attributes", {}),
                "relationships": {"item_type": {"data": {"type": "item_type", "id": merged.get("model_id", "")}}},
            }
        })
        r.raise_for_status()
    return r.json()


@register_node("datocms.update_item")
async def datocms_update_item(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    item_id = merged.get("item_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.put(f"{BASE}/items/{item_id}", json={
            "data": {"type": "item", "id": item_id, "attributes": merged.get("attributes", {})}
        })
        r.raise_for_status()
    return r.json()
