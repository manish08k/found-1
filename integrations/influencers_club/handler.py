"""Influencers Club integration — influencer marketing platform."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.influencers.club/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("influencers_club.search_influencers")
async def influencers_club_search_influencers(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/search", json={
            "niche": merged.get("niche", ""),
            "platform": merged.get("platform", "instagram"),
            "min_followers": merged.get("min_followers", 1000),
        })
        r.raise_for_status()
    return {"influencers": r.json()}


@register_node("influencers_club.get_influencer")
async def influencers_club_get_influencer(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    influencer_id = merged.get("influencer_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/influencers/{influencer_id}")
        r.raise_for_status()
    return r.json()
