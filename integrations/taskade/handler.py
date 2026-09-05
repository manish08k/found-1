"""Taskade collaborative workspace integration — workspaces, projects, and tasks."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

TASKADE_BASE = "https://www.taskade.com/api/v1"


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}


@register_node("taskade.list_workspaces")
async def taskade_list_workspaces(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Taskade workspaces for the authenticated user.

    config:
      api_key — Taskade API key / access token (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for taskade.list_workspaces")

    async with httpx.AsyncClient(base_url=TASKADE_BASE, timeout=30) as client:
        r = await client.get("/workspaces", headers=_headers(api_key))
        r.raise_for_status()
        data = r.json()

    workspaces = data.get("items", data) if isinstance(data, dict) else data
    log.info("taskade.list_workspaces", count=len(workspaces))
    return {"workspaces": workspaces, "count": len(workspaces)}


@register_node("taskade.list_projects")
async def taskade_list_projects(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List projects inside a Taskade workspace.

    config:
      api_key      — Taskade API key (required)
      workspace_id — workspace ID (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for taskade.list_projects")

    workspace_id = config.get("workspace_id") or input_data.get("workspace_id")
    if not workspace_id:
        raise ValueError("workspace_id is required for taskade.list_projects")

    async with httpx.AsyncClient(base_url=TASKADE_BASE, timeout=30) as client:
        r = await client.get(f"/workspaces/{workspace_id}/projects", headers=_headers(api_key))
        r.raise_for_status()
        data = r.json()

    projects = data.get("items", data) if isinstance(data, dict) else data
    log.info("taskade.list_projects", workspace_id=workspace_id, count=len(projects))
    return {"projects": projects, "count": len(projects)}


@register_node("taskade.create_task")
async def taskade_create_task(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a task in a Taskade project.

    config/input_data:
      api_key    — Taskade API key (required)
      project_id — project ID (required)
      name       — task text / title (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for taskade.create_task")

    project_id = config.get("project_id") or input_data.get("project_id")
    name = config.get("name") or input_data.get("name")
    if not project_id or not name:
        raise ValueError("project_id and name are required for taskade.create_task")

    payload = {"tasks": [{"text": name}]}

    async with httpx.AsyncClient(base_url=TASKADE_BASE, timeout=30) as client:
        r = await client.post(f"/projects/{project_id}/tasks", json=payload, headers=_headers(api_key))
        r.raise_for_status()
        data = r.json()

    log.info("taskade.create_task", project_id=project_id, name=name)
    return {"result": data, "project_id": project_id}


@register_node("taskade.list_tasks")
async def taskade_list_tasks(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List tasks in a Taskade project.

    config:
      api_key    — Taskade API key (required)
      project_id — project ID (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for taskade.list_tasks")

    project_id = config.get("project_id") or input_data.get("project_id")
    if not project_id:
        raise ValueError("project_id is required for taskade.list_tasks")

    async with httpx.AsyncClient(base_url=TASKADE_BASE, timeout=30) as client:
        r = await client.get(f"/projects/{project_id}/tasks", headers=_headers(api_key))
        r.raise_for_status()
        data = r.json()

    tasks = data.get("items", data) if isinstance(data, dict) else data
    log.info("taskade.list_tasks", project_id=project_id, count=len(tasks))
    return {"tasks": tasks, "count": len(tasks)}
