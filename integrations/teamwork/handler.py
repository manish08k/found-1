"""Teamwork project management integration — projects, tasks, and people."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _client(site: str, api_key: str) -> httpx.AsyncClient:
    """Build an authenticated async client for the Teamwork site."""
    base_url = f"https://{site}.teamwork.com"
    return httpx.AsyncClient(base_url=base_url, auth=(api_key, ""), timeout=30)


@register_node("teamwork.list_projects")
async def teamwork_list_projects(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Teamwork projects.

    config:
      api_key — Teamwork API key (required)
      site    — Teamwork site subdomain, e.g. "mycompany" (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    site = config.get("site") or input_data.get("site")
    if not api_key or not site:
        raise ValueError("api_key and site are required for teamwork.list_projects")

    async with _client(site, api_key) as client:
        r = await client.get("/projects.json")
        r.raise_for_status()
        data = r.json()

    projects = data.get("projects", [])
    log.info("teamwork.list_projects", site=site, count=len(projects))
    return {"projects": projects, "count": len(projects)}


@register_node("teamwork.create_task")
async def teamwork_create_task(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a task in a Teamwork task list.

    config/input_data:
      api_key      — Teamwork API key (required)
      site         — Teamwork site subdomain (required)
      task_list_id — task list ID to add the task to (required)
      name         — task content / name (required)
      desc         — task description (optional)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    site = config.get("site") or input_data.get("site")
    if not api_key or not site:
        raise ValueError("api_key and site are required for teamwork.create_task")

    task_list_id = config.get("task_list_id") or input_data.get("task_list_id")
    name = config.get("name") or input_data.get("name")
    if not task_list_id or not name:
        raise ValueError("task_list_id and name are required for teamwork.create_task")

    desc = config.get("desc") or input_data.get("desc", "")
    payload = {"todo-item": {"content": name, "description": desc}}

    async with _client(site, api_key) as client:
        r = await client.post(f"/tasklists/{task_list_id}/tasks.json", json=payload)
        r.raise_for_status()
        data = r.json()

    task_id = data.get("id")
    log.info("teamwork.create_task", task_id=task_id, name=name)
    return {"result": data, "task_id": task_id}


@register_node("teamwork.list_tasks")
async def teamwork_list_tasks(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all tasks in Teamwork.

    config:
      api_key — Teamwork API key (required)
      site    — Teamwork site subdomain (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    site = config.get("site") or input_data.get("site")
    if not api_key or not site:
        raise ValueError("api_key and site are required for teamwork.list_tasks")

    async with _client(site, api_key) as client:
        r = await client.get("/tasks.json")
        r.raise_for_status()
        data = r.json()

    tasks = data.get("todo-items", [])
    log.info("teamwork.list_tasks", site=site, count=len(tasks))
    return {"tasks": tasks, "count": len(tasks)}


@register_node("teamwork.list_people")
async def teamwork_list_people(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all people in a Teamwork account.

    config:
      api_key — Teamwork API key (required)
      site    — Teamwork site subdomain (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    site = config.get("site") or input_data.get("site")
    if not api_key or not site:
        raise ValueError("api_key and site are required for teamwork.list_people")

    async with _client(site, api_key) as client:
        r = await client.get("/people.json")
        r.raise_for_status()
        data = r.json()

    people = data.get("people", [])
    log.info("teamwork.list_people", site=site, count=len(people))
    return {"people": people, "count": len(people)}
