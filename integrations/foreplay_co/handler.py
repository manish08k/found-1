"""Foreplay integration — ad creative research and inspiration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.foreplay.co/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("foreplay_co.search_ads")
async def foreplay_co_search_ads(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/ads/search", params={"query": merged.get("query", ""), "limit": merged.get("limit", 10)})
        r.raise_for_status()
    return {"ads": r.json()}


@register_node("foreplay_co.save_ad")
async def foreplay_co_save_ad(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/saved-ads", json={"ad_id": merged.get("ad_id", ""), "board_id": merged.get("board_id", "")})
        r.raise_for_status()
    return r.json()
