"""Motion AI task management integration — tasks and projects."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

MOTION_BASE = "https://api.usemotion.com/v1"


def _headers(api_key: str) -> dict:
    return {"X-API-Key": api_key, "Accept": "application/json"}


@register_node("motion.list_tasks")
async def motion_list_tasks(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List tasks for a Motion workspace.

    config:
      api_key       — Motion API key (required)
      workspace_id  — workspace ID to filter tasks (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for motion.list_tasks")

    workspace_id = config.get("workspace_id") or input_data.get("workspace_id")
    if not workspace_id:
        raise ValueError("workspace_id is required for motion.list_tasks")

    async with httpx.AsyncClient(base_url=MOTION_BASE, timeout=30) as client:
        r = await client.get("/tasks", params={"workspaceId": workspace_id}, headers=_headers(api_key))
        r.raise_for_status()
        data = r.json()

    tasks = data.get("tasks", data) if isinstance(data, dict) else data
    log.info("motion.list_tasks", workspace_id=workspace_id, count=len(tasks))
    return {"tasks": tasks, "count": len(tasks)}


@register_node("motion.create_task")
async def motion_create_task(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a task in Motion.

    config/input_data:
      api_key       — Motion API key (required)
      workspace_id  — workspace ID (required)
      name          — task name (required)
      due_date      — ISO 8601 due date (optional)
      priority      — priority level (default: MEDIUM)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for motion.create_task")

    workspace_id = config.get("workspace_id") or input_data.get("workspace_id")
    name = config.get("name") or input_data.get("name")
    if not workspace_id or not name:
        raise ValueError("workspace_id and name are required for motion.create_task")

    due_date = config.get("due_date") or input_data.get("due_date")
    priority = config.get("priority") or input_data.get("priority", "MEDIUM")

    payload: dict = {"name": name, "workspaceId": workspace_id, "priority": priority}
    if due_date:
        payload["dueDate"] = due_date

    async with httpx.AsyncClient(base_url=MOTION_BASE, timeout=30) as client:
        r = await client.post("/tasks", json=payload, headers=_headers(api_key))
        r.raise_for_status()
        task = r.json()

    log.info("motion.create_task", task_id=task.get("id"), name=name)
    return {"task": task, "task_id": task.get("id")}


@register_node("motion.update_task")
async def motion_update_task(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update a Motion task by ID.

    config/input_data:
      api_key   — Motion API key (required)
      task_id   — ID of the task to update (required)
      fields    — dict of fields to update (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for motion.update_task")

    task_id = config.get("task_id") or input_data.get("task_id")
    if not task_id:
        raise ValueError("task_id is required for motion.update_task")

    fields = config.get("fields") or input_data.get("fields") or {}

    async with httpx.AsyncClient(base_url=MOTION_BASE, timeout=30) as client:
        r = await client.patch(f"/tasks/{task_id}", json=fields, headers=_headers(api_key))
        r.raise_for_status()
        task = r.json()

    log.info("motion.update_task", task_id=task_id)
    return {"task": task, "task_id": task_id}


@register_node("motion.list_projects")
async def motion_list_projects(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List projects in a Motion workspace.

    config:
      api_key       — Motion API key (required)
      workspace_id  — workspace ID (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for motion.list_projects")

    workspace_id = config.get("workspace_id") or input_data.get("workspace_id")
    if not workspace_id:
        raise ValueError("workspace_id is required for motion.list_projects")

    async with httpx.AsyncClient(base_url=MOTION_BASE, timeout=30) as client:
        r = await client.get("/projects", params={"workspaceId": workspace_id}, headers=_headers(api_key))
        r.raise_for_status()
        data = r.json()

    projects = data.get("projects", data) if isinstance(data, dict) else data
    log.info("motion.list_projects", workspace_id=workspace_id, count=len(projects))
    return {"projects": projects, "count": len(projects)}
