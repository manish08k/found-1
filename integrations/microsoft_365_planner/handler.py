"""Microsoft 365 Planner integration — manage plans and tasks via Microsoft Graph API."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _graph_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


@register_node("microsoft_365_planner.list_plans")
async def microsoft_365_planner_list_plans(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List Planner plans for a Microsoft 365 group.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      group_id     — Microsoft 365 group ID to list plans for (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    group_id = merged.get("group_id")
    if not group_id:
        raise ValueError("group_id is required for microsoft_365_planner.list_plans")

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.get(f"/groups/{group_id}/planner/plans", headers=_graph_headers(access_token))
        r.raise_for_status()
        data = r.json()

    plans = data.get("value", [])
    log.info("microsoft_365_planner.list_plans", group_id=group_id, count=len(plans))
    return {"plans": plans, "count": len(plans)}


@register_node("microsoft_365_planner.create_task")
async def microsoft_365_planner_create_task(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new Planner task.

    config/input_data:
      access_token  — Microsoft Graph OAuth2 bearer token (required)
      plan_id       — Planner plan ID (required)
      title         — task title (required)
      bucket_id     — bucket ID to place the task in (optional)
      assigned_to   — list of user IDs to assign (optional)
      due_date_time — ISO 8601 due date/time (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    plan_id = merged.get("plan_id")
    title = merged.get("title")
    if not plan_id:
        raise ValueError("plan_id is required for microsoft_365_planner.create_task")
    if not title:
        raise ValueError("title is required for microsoft_365_planner.create_task")

    payload: dict = {"planId": plan_id, "title": title}
    if merged.get("bucket_id"):
        payload["bucketId"] = merged["bucket_id"]
    if merged.get("due_date_time"):
        payload["dueDateTime"] = merged["due_date_time"]
    if merged.get("assigned_to"):
        assignments = {}
        for user_id in merged["assigned_to"]:
            assignments[user_id] = {"@odata.type": "#microsoft.graph.plannerAssignment", "orderHint": " !"}
        payload["assignments"] = assignments

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.post("/planner/tasks", headers=_graph_headers(access_token), json=payload)
        r.raise_for_status()
        task = r.json()

    log.info("microsoft_365_planner.create_task", task_id=task.get("id"), plan_id=plan_id)
    return {"task": task, "task_id": task.get("id")}


@register_node("microsoft_365_planner.get_task")
async def microsoft_365_planner_get_task(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a specific Planner task by ID.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      task_id      — Planner task ID to retrieve (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    task_id = merged.get("task_id")
    if not task_id:
        raise ValueError("task_id is required for microsoft_365_planner.get_task")

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.get(f"/planner/tasks/{task_id}", headers=_graph_headers(access_token))
        r.raise_for_status()
        task = r.json()

    log.info("microsoft_365_planner.get_task", task_id=task_id)
    return {"task": task, "task_id": task_id}


@register_node("microsoft_365_planner.update_task")
async def microsoft_365_planner_update_task(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update an existing Planner task.

    config/input_data:
      access_token    — Microsoft Graph OAuth2 bearer token (required)
      task_id         — Planner task ID to update (required)
      etag            — ETag for optimistic concurrency (required)
      title           — new task title (optional)
      percent_complete — completion percentage 0-100 (optional)
      due_date_time   — ISO 8601 due date/time (optional)
      bucket_id       — bucket ID to move the task to (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    task_id = merged.get("task_id")
    etag = merged.get("etag", "*")
    if not task_id:
        raise ValueError("task_id is required for microsoft_365_planner.update_task")

    payload: dict = {}
    if merged.get("title"):
        payload["title"] = merged["title"]
    if merged.get("percent_complete") is not None:
        payload["percentComplete"] = merged["percent_complete"]
    if merged.get("due_date_time"):
        payload["dueDateTime"] = merged["due_date_time"]
    if merged.get("bucket_id"):
        payload["bucketId"] = merged["bucket_id"]

    headers = {**_graph_headers(access_token), "If-Match": etag}

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.patch(f"/planner/tasks/{task_id}", headers=headers, json=payload)
        r.raise_for_status()
        task = r.json() if r.content else {"task_id": task_id, "updated": True}

    log.info("microsoft_365_planner.update_task", task_id=task_id)
    return {"task": task, "task_id": task_id}


@register_node("microsoft_365_planner.list_tasks")
async def microsoft_365_planner_list_tasks(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List tasks in a Planner plan.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      plan_id      — Planner plan ID (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    plan_id = merged.get("plan_id")
    if not plan_id:
        raise ValueError("plan_id is required for microsoft_365_planner.list_tasks")

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.get(f"/planner/plans/{plan_id}/tasks", headers=_graph_headers(access_token))
        r.raise_for_status()
        data = r.json()

    tasks = data.get("value", [])
    log.info("microsoft_365_planner.list_tasks", plan_id=plan_id, count=len(tasks))
    return {"tasks": tasks, "count": len(tasks)}
