"""TickTick task manager integration — projects and tasks."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

TICKTICK_BASE = "https://api.ticktick.com/open/v1"


def _headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}


@register_node("ticktick.list_projects")
async def ticktick_list_projects(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all TickTick projects (lists) for the authenticated user.

    config:
      access_token — OAuth2 access token (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for ticktick.list_projects")

    async with httpx.AsyncClient(base_url=TICKTICK_BASE, timeout=30) as client:
        r = await client.get("/project", headers=_headers(access_token))
        r.raise_for_status()
        projects = r.json()

    log.info("ticktick.list_projects", count=len(projects))
    return {"projects": projects, "count": len(projects)}


@register_node("ticktick.get_project")
async def ticktick_get_project(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single TickTick project by ID.

    config/input_data:
      access_token — OAuth2 access token (required)
      project_id   — project ID (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for ticktick.get_project")

    project_id = config.get("project_id") or input_data.get("project_id")
    if not project_id:
        raise ValueError("project_id is required for ticktick.get_project")

    async with httpx.AsyncClient(base_url=TICKTICK_BASE, timeout=30) as client:
        r = await client.get(f"/project/{project_id}", headers=_headers(access_token))
        r.raise_for_status()
        project = r.json()

    log.info("ticktick.get_project", project_id=project_id)
    return {"project": project}


@register_node("ticktick.create_task")
async def ticktick_create_task(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a task in TickTick.

    config/input_data:
      access_token — OAuth2 access token (required)
      title        — task title (required)
      project_id   — project/list ID (required)
      due_date     — ISO 8601 due date string (optional)
      priority     — priority 0=none, 1=low, 3=medium, 5=high (default 0)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for ticktick.create_task")

    title = config.get("title") or input_data.get("title")
    project_id = config.get("project_id") or input_data.get("project_id")
    if not title or not project_id:
        raise ValueError("title and project_id are required for ticktick.create_task")

    due_date = config.get("due_date") or input_data.get("due_date")
    priority = int(config.get("priority", input_data.get("priority", 0)))

    payload: dict = {"title": title, "projectId": project_id, "priority": priority}
    if due_date:
        payload["dueDate"] = due_date

    async with httpx.AsyncClient(base_url=TICKTICK_BASE, timeout=30) as client:
        r = await client.post("/task", json=payload, headers=_headers(access_token))
        r.raise_for_status()
        task = r.json()

    log.info("ticktick.create_task", task_id=task.get("id"), title=title)
    return {"task": task, "task_id": task.get("id")}


@register_node("ticktick.update_task")
async def ticktick_update_task(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update an existing TickTick task.

    config/input_data:
      access_token — OAuth2 access token (required)
      task_id      — ID of the task to update (required)
      fields       — dict of fields to update (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for ticktick.update_task")

    task_id = config.get("task_id") or input_data.get("task_id")
    if not task_id:
        raise ValueError("task_id is required for ticktick.update_task")

    fields = config.get("fields") or input_data.get("fields") or {}

    async with httpx.AsyncClient(base_url=TICKTICK_BASE, timeout=30) as client:
        r = await client.post(f"/task/{task_id}", json=fields, headers=_headers(access_token))
        r.raise_for_status()
        task = r.json()

    log.info("ticktick.update_task", task_id=task_id)
    return {"task": task, "task_id": task_id}


@register_node("ticktick.complete_task")
async def ticktick_complete_task(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Mark a TickTick task as complete.

    config/input_data:
      access_token — OAuth2 access token (required)
      project_id   — project/list ID (required)
      task_id      — task ID (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for ticktick.complete_task")

    project_id = config.get("project_id") or input_data.get("project_id")
    task_id = config.get("task_id") or input_data.get("task_id")
    if not project_id or not task_id:
        raise ValueError("project_id and task_id are required for ticktick.complete_task")

    async with httpx.AsyncClient(base_url=TICKTICK_BASE, timeout=30) as client:
        r = await client.post(
            f"/project/{project_id}/task/{task_id}/complete",
            headers=_headers(access_token),
        )
        r.raise_for_status()

    log.info("ticktick.complete_task", project_id=project_id, task_id=task_id)
    return {"success": True, "task_id": task_id, "project_id": project_id}
