"""Wrike project management integration — folders, tasks."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

WRIKE_BASE = "https://www.wrike.com/api/v4"


def _headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}


@register_node("wrike.list_folders")
async def wrike_list_folders(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Wrike folders.

    config:
      access_token — Wrike OAuth2 access token (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for wrike.list_folders")

    async with httpx.AsyncClient(base_url=WRIKE_BASE, timeout=30) as client:
        r = await client.get("/folders", headers=_headers(access_token))
        r.raise_for_status()
        data = r.json()

    folders = data.get("data", [])
    log.info("wrike.list_folders", count=len(folders))
    return {"folders": folders, "count": len(folders)}


@register_node("wrike.list_tasks")
async def wrike_list_tasks(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List active Wrike tasks.

    config:
      access_token — Wrike OAuth2 access token (required)
      limit        — max tasks to return (default 25)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for wrike.list_tasks")

    limit = int(config.get("limit", 25))

    async with httpx.AsyncClient(base_url=WRIKE_BASE, timeout=30) as client:
        r = await client.get(
            "/tasks",
            params={"status": "Active", "limit": limit},
            headers=_headers(access_token),
        )
        r.raise_for_status()
        data = r.json()

    tasks = data.get("data", [])
    log.info("wrike.list_tasks", count=len(tasks))
    return {"tasks": tasks, "count": len(tasks)}


@register_node("wrike.create_task")
async def wrike_create_task(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a task inside a Wrike folder.

    config/input_data:
      access_token — Wrike OAuth2 access token (required)
      folder_id    — folder ID to create the task in (required)
      title        — task title (required)
      desc         — task description (optional)
      status       — task status (default: Active)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for wrike.create_task")

    folder_id = config.get("folder_id") or input_data.get("folder_id")
    title = config.get("title") or input_data.get("title")
    if not folder_id or not title:
        raise ValueError("folder_id and title are required for wrike.create_task")

    desc = config.get("desc") or input_data.get("desc", "")
    status = config.get("status") or input_data.get("status", "Active")
    payload = {"title": title, "description": desc, "status": status}

    async with httpx.AsyncClient(base_url=WRIKE_BASE, timeout=30) as client:
        r = await client.post(
            f"/folders/{folder_id}/tasks",
            json=payload,
            headers=_headers(access_token),
        )
        r.raise_for_status()
        data = r.json()

    task = data.get("data", [{}])[0]
    log.info("wrike.create_task", task_id=task.get("id"), title=title)
    return {"task": task, "task_id": task.get("id")}


@register_node("wrike.get_task")
async def wrike_get_task(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single Wrike task by ID.

    config/input_data:
      access_token — Wrike OAuth2 access token (required)
      task_id      — task ID (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for wrike.get_task")

    task_id = config.get("task_id") or input_data.get("task_id")
    if not task_id:
        raise ValueError("task_id is required for wrike.get_task")

    async with httpx.AsyncClient(base_url=WRIKE_BASE, timeout=30) as client:
        r = await client.get(f"/tasks/{task_id}", headers=_headers(access_token))
        r.raise_for_status()
        data = r.json()

    task = data.get("data", [{}])[0]
    log.info("wrike.get_task", task_id=task_id)
    return {"task": task}
