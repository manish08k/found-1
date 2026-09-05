"""Nifty project management integration — projects, tasks, and milestones."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

NIFTY_BASE = "https://openapi.niftypm.com/api/v1.0"


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}


@register_node("nifty.list_projects")
async def nifty_list_projects(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Nifty projects.

    config:
      api_key — Nifty API key (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for nifty.list_projects")

    async with httpx.AsyncClient(base_url=NIFTY_BASE, timeout=30) as client:
        r = await client.get("/projects", headers=_headers(api_key))
        r.raise_for_status()
        data = r.json()

    projects = data.get("items", data) if isinstance(data, dict) else data
    log.info("nifty.list_projects", count=len(projects))
    return {"projects": projects, "count": len(projects)}


@register_node("nifty.list_tasks")
async def nifty_list_tasks(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List tasks in a Nifty project.

    config:
      api_key    — Nifty API key (required)
      project_id — project ID to filter tasks (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for nifty.list_tasks")

    project_id = config.get("project_id") or input_data.get("project_id")
    if not project_id:
        raise ValueError("project_id is required for nifty.list_tasks")

    async with httpx.AsyncClient(base_url=NIFTY_BASE, timeout=30) as client:
        r = await client.get("/tasks", params={"project_id": project_id}, headers=_headers(api_key))
        r.raise_for_status()
        data = r.json()

    tasks = data.get("items", data) if isinstance(data, dict) else data
    log.info("nifty.list_tasks", project_id=project_id, count=len(tasks))
    return {"tasks": tasks, "count": len(tasks)}


@register_node("nifty.create_task")
async def nifty_create_task(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a task in a Nifty project.

    config/input_data:
      api_key    — Nifty API key (required)
      name       — task name (required)
      project_id — project ID (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for nifty.create_task")

    name = config.get("name") or input_data.get("name")
    project_id = config.get("project_id") or input_data.get("project_id")
    if not name or not project_id:
        raise ValueError("name and project_id are required for nifty.create_task")

    payload = {"name": name, "project_id": project_id}

    async with httpx.AsyncClient(base_url=NIFTY_BASE, timeout=30) as client:
        r = await client.post("/tasks", json=payload, headers=_headers(api_key))
        r.raise_for_status()
        task = r.json()

    log.info("nifty.create_task", task_id=task.get("id"), name=name)
    return {"task": task, "task_id": task.get("id")}


@register_node("nifty.list_milestones")
async def nifty_list_milestones(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List milestones for a Nifty project.

    config:
      api_key    — Nifty API key (required)
      project_id — project ID (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for nifty.list_milestones")

    project_id = config.get("project_id") or input_data.get("project_id")
    if not project_id:
        raise ValueError("project_id is required for nifty.list_milestones")

    async with httpx.AsyncClient(base_url=NIFTY_BASE, timeout=30) as client:
        r = await client.get("/milestones", params={"project_id": project_id}, headers=_headers(api_key))
        r.raise_for_status()
        data = r.json()

    milestones = data.get("items", data) if isinstance(data, dict) else data
    log.info("nifty.list_milestones", project_id=project_id, count=len(milestones))
    return {"milestones": milestones, "count": len(milestones)}
