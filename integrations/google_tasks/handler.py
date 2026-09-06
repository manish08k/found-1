"""Google Tasks integration — task management."""
import httpx
import structlog
from core.execution_engine import register_node
from oauth.flow import get_access_token

log = structlog.get_logger(__name__)
BASE = "https://tasks.googleapis.com/tasks/v1"


async def _headers(credential_id: str, db) -> dict:
    token = await get_access_token(credential_id, db)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@register_node("google_tasks.list_task_lists")
async def google_tasks_list_task_lists(config: dict, input_data: dict, credential_id: str, db) -> dict:
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.get(f"{BASE}/users/@me/lists")
        r.raise_for_status()
    return {"task_lists": r.json().get("items", [])}


@register_node("google_tasks.list_tasks")
async def google_tasks_list_tasks(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    tasklist_id = merged.get("tasklist_id", "@default")
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.get(f"{BASE}/lists/{tasklist_id}/tasks")
        r.raise_for_status()
    return {"tasks": r.json().get("items", [])}


@register_node("google_tasks.create_task")
async def google_tasks_create_task(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    tasklist_id = merged.get("tasklist_id", "@default")
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.post(f"{BASE}/lists/{tasklist_id}/tasks", json={
            "title": merged.get("title", ""),
            "notes": merged.get("notes", ""),
            "due": merged.get("due", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("google_tasks.complete_task")
async def google_tasks_complete_task(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    tasklist_id = merged.get("tasklist_id", "@default")
    task_id = merged.get("task_id", "")
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.patch(f"{BASE}/lists/{tasklist_id}/tasks/{task_id}", json={"status": "completed"})
        r.raise_for_status()
    return r.json()
