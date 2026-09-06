"""GoodMem integration — memory and knowledge base management."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.goodmem.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("goodmem.add_memory")
async def goodmem_add_memory(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/memories", json={
            "content": merged.get("content", ""),
            "tags": merged.get("tags", []),
        })
        r.raise_for_status()
    return r.json()


@register_node("goodmem.search_memory")
async def goodmem_search_memory(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/memories/search", json={"query": merged.get("query", "")})
        r.raise_for_status()
    return {"memories": r.json()}
