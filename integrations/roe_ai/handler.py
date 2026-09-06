"""Roe AI integration — data and business intelligence platform."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://app.roe.ai/api/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("roe_ai.run_query")
async def roe_ai_run_query(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/query", json={"query": merged.get("query", ""), "natural_language": merged.get("use_nl", True)})
        r.raise_for_status()
    return r.json()


@register_node("roe_ai.get_datasets")
async def roe_ai_get_datasets(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/datasets")
        r.raise_for_status()
    return {"datasets": r.json()}
