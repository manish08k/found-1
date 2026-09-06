"""Hedy integration — learning platform for programming education."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://hedy.org/api/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("hedy.get_programs")
async def hedy_get_programs(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/programs")
        r.raise_for_status()
    return {"programs": r.json()}


@register_node("hedy.run_code")
async def hedy_run_code(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/run", json={
            "code": merged.get("code", ""),
            "level": merged.get("level", 1),
            "language": merged.get("language", "en"),
        })
        r.raise_for_status()
    return r.json()
