"""SocialKit integration — social media growth tools."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.socialkit.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("socialkit.schedule_post")
async def socialkit_schedule_post(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/posts", json={
            "content": merged.get("content", ""),
            "platforms": merged.get("platforms", []),
            "scheduled_time": merged.get("scheduled_time", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("socialkit.get_analytics")
async def socialkit_get_analytics(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/analytics", params={"period": merged.get("period", "7d")})
        r.raise_for_status()
    return r.json()
