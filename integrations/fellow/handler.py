"""Fellow integration — meeting management and action items."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.fellow.app/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("fellow.get_meetings")
async def fellow_get_meetings(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/meetings", params={"limit": merged.get("limit", 10)})
        r.raise_for_status()
    return {"meetings": r.json()}


@register_node("fellow.create_action_item")
async def fellow_create_action_item(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/action-items", json={
            "title": merged.get("title", ""),
            "assignee_id": merged.get("assignee_id", ""),
            "due_date": merged.get("due_date", ""),
            "meeting_id": merged.get("meeting_id", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("fellow.get_action_items")
async def fellow_get_action_items(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/action-items", params={"status": merged.get("status", "open")})
        r.raise_for_status()
    return {"action_items": r.json()}
