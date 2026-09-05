"""MeisterTask project management integration — projects and tasks."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

MEISTERTASK_BASE = "https://www.meistertask.com/api"


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}


@register_node("meistertask.list_projects")
async def meistertask_list_projects(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all MeisterTask projects accessible by the API key.

    config:
      api_key — MeisterTask API key (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for meistertask.list_projects")

    async with httpx.AsyncClient(base_url=MEISTERTASK_BASE, timeout=30) as client:
        r = await client.get("/projects", headers=_headers(api_key))
        r.raise_for_status()
        projects = r.json()

    log.info("meistertask.list_projects", count=len(projects))
    return {"projects": projects, "count": len(projects)}


@register_node("meistertask.get_project")
async def meistertask_get_project(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single MeisterTask project by ID.

    config/input_data:
      api_key    — MeisterTask API key (required)
      project_id — project ID (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for meistertask.get_project")

    project_id = config.get("project_id") or input_data.get("project_id")
    if not project_id:
        raise ValueError("project_id is required for meistertask.get_project")

    async with httpx.AsyncClient(base_url=MEISTERTASK_BASE, timeout=30) as client:
        r = await client.get(f"/projects/{project_id}", headers=_headers(api_key))
        r.raise_for_status()
        project = r.json()

    log.info("meistertask.get_project", project_id=project_id)
    return {"project": project}


@register_node("meistertask.list_tasks")
async def meistertask_list_tasks(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List tasks in a MeisterTask project.

    config:
      api_key    — MeisterTask API key (required)
      project_id — project ID to list tasks for (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for meistertask.list_tasks")

    project_id = config.get("project_id") or input_data.get("project_id")
    if not project_id:
        raise ValueError("project_id is required for meistertask.list_tasks")

    async with httpx.AsyncClient(base_url=MEISTERTASK_BASE, timeout=30) as client:
        r = await client.get(f"/projects/{project_id}/tasks", headers=_headers(api_key))
        r.raise_for_status()
        tasks = r.json()

    log.info("meistertask.list_tasks", project_id=project_id, count=len(tasks))
    return {"tasks": tasks, "count": len(tasks)}


@register_node("meistertask.create_task")
async def meistertask_create_task(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a task in a MeisterTask section.

    config/input_data:
      api_key    — MeisterTask API key (required)
      section_id — section ID to create the task in (required)
      name       — task name (required)
      desc       — task description / notes (optional)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for meistertask.create_task")

    section_id = config.get("section_id") or input_data.get("section_id")
    name = config.get("name") or input_data.get("name")
    if not section_id or not name:
        raise ValueError("section_id and name are required for meistertask.create_task")

    desc = config.get("desc") or input_data.get("desc", "")
    payload = {"name": name, "notes": desc}

    async with httpx.AsyncClient(base_url=MEISTERTASK_BASE, timeout=30) as client:
        r = await client.post(f"/sections/{section_id}/tasks", json=payload, headers=_headers(api_key))
        r.raise_for_status()
        task = r.json()

    log.info("meistertask.create_task", task_id=task.get("id"), name=name)
    return {"task": task, "task_id": task.get("id")}
