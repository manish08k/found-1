"""LetMePost integration — social media scheduling."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://letmepost.io/api/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("letmepost.schedule_post")
async def letmepost_schedule_post(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/posts", json={
            "content": merged.get("content", ""),
            "platforms": merged.get("platforms", []),
            "scheduled_at": merged.get("scheduled_at", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("letmepost.get_posts")
async def letmepost_get_posts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/posts", params={"status": merged.get("status", "all")})
        r.raise_for_status()
    return {"posts": r.json()}
