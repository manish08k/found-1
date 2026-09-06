"""Mem integration — AI-powered note-taking."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.mem.ai/v0"


def _headers(config: dict) -> dict:
    return {"Authorization": f"ApiAccessToken {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("mem.create_mem")
async def mem_create_mem(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/mems", json={
            "content": merged.get("content", ""),
            "isRead": merged.get("is_read", False),
        })
        r.raise_for_status()
    return r.json()


@register_node("mem.search_mems")
async def mem_search_mems(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/search", json={"query": merged.get("query", "")})
        r.raise_for_status()
    return {"results": r.json()}
