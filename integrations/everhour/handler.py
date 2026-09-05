"""Everhour — time tracking integration."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

EVERHOUR_BASE = "https://api.everhour.com/api"


def _headers(config: dict) -> dict:
    api_key = config.get("api_key", "")
    return {
        "X-Api-Key": api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


@register_node("everhour.list_projects")
async def everhour_list_projects(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List projects from Everhour.

    config:
      api_key — Everhour API key
      limit   — number of projects to return (default 25)
    """
    limit = int(config.get("limit", 25))

    async with httpx.AsyncClient(base_url=EVERHOUR_BASE, timeout=30) as client:
        r = await client.get("/projects", params={"limit": limit}, headers=_headers(config))
        r.raise_for_status()
        data = r.json()

    projects = data if isinstance(data, list) else data.get("projects", [])
    log.info("everhour.list_projects", count=len(projects))
    return {"projects": projects, "count": len(projects)}


@register_node("everhour.list_tasks")
async def everhour_list_tasks(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List tasks for a project in Everhour.

    config/input_data:
      api_key    — Everhour API key
      project_id — project ID to list tasks for (required; can also be set in config)
    """
    project_id = config.get("project_id") or input_data.get("project_id")
    if not project_id:
        raise ValueError("project_id is required for everhour.list_tasks")

    async with httpx.AsyncClient(base_url=EVERHOUR_BASE, timeout=30) as client:
        r = await client.get(f"/projects/{project_id}/tasks", headers=_headers(config))
        r.raise_for_status()
        data = r.json()

    tasks = data if isinstance(data, list) else data.get("tasks", [])
    log.info("everhour.list_tasks", project_id=project_id, count=len(tasks))
    return {"tasks": tasks, "count": len(tasks), "project_id": project_id}


@register_node("everhour.log_time")
async def everhour_log_time(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Log time to a task in Everhour.

    config/input_data:
      api_key — Everhour API key
      task_id — task ID to log time against (required)
      seconds — number of seconds to log (required)
      date    — date for the time entry in YYYY-MM-DD format (required)
    """
    task_id = config.get("task_id") or input_data.get("task_id")
    seconds = config.get("seconds") or input_data.get("seconds")
    date = config.get("date") or input_data.get("date")

    if not task_id:
        raise ValueError("task_id is required for everhour.log_time")
    if seconds is None:
        raise ValueError("seconds is required for everhour.log_time")
    if not date:
        raise ValueError("date is required for everhour.log_time")

    payload = {"time": int(seconds), "date": date}

    async with httpx.AsyncClient(base_url=EVERHOUR_BASE, timeout=30) as client:
        r = await client.post(f"/tasks/{task_id}/time", json=payload, headers=_headers(config))
        r.raise_for_status()
        result = r.json()

    log.info("everhour.log_time", task_id=task_id, seconds=seconds, date=date)
    return {"time_entry": result, "task_id": task_id, "seconds": int(seconds), "date": date}


@register_node("everhour.get_report")
async def everhour_get_report(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a team time report from Everhour for a date range.

    config/input_data:
      api_key   — Everhour API key
      from_date — report start date in YYYY-MM-DD format (required)
      to_date   — report end date in YYYY-MM-DD format (required)
    """
    from_date = config.get("from_date") or input_data.get("from_date")
    to_date = config.get("to_date") or input_data.get("to_date")

    if not from_date:
        raise ValueError("from_date is required for everhour.get_report")
    if not to_date:
        raise ValueError("to_date is required for everhour.get_report")

    async with httpx.AsyncClient(base_url=EVERHOUR_BASE, timeout=30) as client:
        r = await client.get(
            "/team/time",
            params={"from": from_date, "to": to_date},
            headers=_headers(config),
        )
        r.raise_for_status()
        report = r.json()

    log.info("everhour.get_report", from_date=from_date, to_date=to_date)
    return {"report": report, "from_date": from_date, "to_date": to_date}
