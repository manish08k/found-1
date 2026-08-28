"""
Asana integration. Credential fields: {"access_token": "..."} — a
Personal Access Token from https://app.asana.com/0/developer-console,
sent as a standard Bearer token.
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

ASANA_BASE = "https://app.asana.com/api/1.0"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    token = creds.get("access_token")
    if not token:
        raise ValueError("Asana credential is missing 'access_token'")
    return httpx.AsyncClient(base_url=ASANA_BASE, headers={"Authorization": f"Bearer {token}"}, timeout=30)


@register_node("asana.create_task")
async def asana_create_task(config: dict, input_data: dict, credential_id: str, db) -> dict:
    project_id = config.get("project_id") or input_data.get("project_id")
    name = config.get("name") or input_data.get("name")
    notes = config.get("notes") or input_data.get("notes", "")
    if not project_id or not name:
        raise ValueError("asana.create_task requires 'project_id' and 'name'")

    payload = {"data": {"name": name, "notes": notes, "projects": [project_id]}}
    async with await _client(credential_id, db) as client:
        r = await client.post("/tasks", json=payload)
        r.raise_for_status()
        data = r.json()["data"]

    return {"gid": data["gid"], "name": data["name"], "permalink_url": data.get("permalink_url")}


@register_node("asana.complete_task")
async def asana_complete_task(config: dict, input_data: dict, credential_id: str, db) -> dict:
    task_gid = config.get("task_gid") or input_data.get("task_gid")
    if not task_gid:
        raise ValueError("asana.complete_task requires 'task_gid'")

    async with await _client(credential_id, db) as client:
        r = await client.put(f"/tasks/{task_gid}", json={"data": {"completed": True}})
        r.raise_for_status()
        data = r.json()["data"]

    return {"gid": data["gid"], "completed": data["completed"]}


@register_node("asana.list_tasks")
async def asana_list_tasks(config: dict, input_data: dict, credential_id: str, db) -> dict:
    project_id = config.get("project_id") or input_data.get("project_id")
    if not project_id:
        raise ValueError("asana.list_tasks requires 'project_id'")

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/projects/{project_id}/tasks", params={"opt_fields": "name,completed,permalink_url"})
        r.raise_for_status()
        data = r.json()["data"]

    return {"tasks": [{"gid": t["gid"], "name": t["name"], "completed": t["completed"]} for t in data]}


async def test_connection(creds: dict) -> None:
    token = creds.get("access_token")
    if not token:
        raise ValueError("Missing access_token")
    async with httpx.AsyncClient(base_url=ASANA_BASE, headers={"Authorization": f"Bearer {token}"}, timeout=10) as client:
        r = await client.get("/users/me")
        r.raise_for_status()
