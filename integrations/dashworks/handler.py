"""Dashworks integration — AI-powered workplace search."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.dashworks.ai/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("dashworks.search")
async def dashworks_search(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/search", json={"query": merged.get("query", "")})
        r.raise_for_status()
    return r.json()


@register_node("dashworks.ask")
async def dashworks_ask(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/ask", json={"question": merged.get("question", "")})
        r.raise_for_status()
    return r.json()
