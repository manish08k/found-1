"""GuideLite integration — interactive product tours and guides."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.guidelite.io/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("guidelite.create_guide")
async def guidelite_create_guide(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/guides", json={
            "name": merged.get("name", ""),
            "steps": merged.get("steps", []),
        })
        r.raise_for_status()
    return r.json()


@register_node("guidelite.get_guides")
async def guidelite_get_guides(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/guides")
        r.raise_for_status()
    return {"guides": r.json()}
