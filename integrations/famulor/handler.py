"""Famulor integration — family management and task coordination."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.famulor.de/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("famulor.create_task")
async def famulor_create_task(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/tasks", json={
            "title": merged.get("title", ""),
            "assignee_id": merged.get("assignee_id", ""),
            "due_date": merged.get("due_date", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("famulor.get_tasks")
async def famulor_get_tasks(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/tasks")
        r.raise_for_status()
    return {"tasks": r.json()}
