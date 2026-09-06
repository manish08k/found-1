"""Microsoft To Do integration — task lists and tasks via Microsoft Graph API."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _graph_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


@register_node("microsoft_todo.list_task_lists")
async def microsoft_todo_list_task_lists(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all task lists in Microsoft To Do.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.get("/me/todo/lists", headers=_graph_headers(access_token))
        r.raise_for_status()
        data = r.json()

    task_lists = data.get("value", [])
    log.info("microsoft_todo.list_task_lists", count=len(task_lists))
    return {"task_lists": task_lists, "count": len(task_lists)}


@register_node("microsoft_todo.create_task")
async def microsoft_todo_create_task(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new task in a Microsoft To Do task list.

    config/input_data:
      access_token        — Microsoft Graph OAuth2 bearer token (required)
      list_id             — task list ID to add the task to (required)
      title               — task title (required)
      body                — task body/notes (optional)
      due_date_time       — due date/time in ISO 8601 format (optional)
      reminder_date_time  — reminder date/time in ISO 8601 format (optional)
      importance          — task importance: "low", "normal", or "high" (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    list_id = merged.get("list_id")
    title = merged.get("title")
    if not list_id:
        raise ValueError("list_id is required for microsoft_todo.create_task")
    if not title:
        raise ValueError("title is required for microsoft_todo.create_task")

    payload: dict = {"title": title}
    if merged.get("body"):
        payload["body"] = {"content": merged["body"], "contentType": "text"}
    if merged.get("due_date_time"):
        payload["dueDateTime"] = {"dateTime": merged["due_date_time"], "timeZone": "UTC"}
    if merged.get("reminder_date_time"):
        payload["reminderDateTime"] = {"dateTime": merged["reminder_date_time"], "timeZone": "UTC"}
        payload["isReminderOn"] = True
    if merged.get("importance"):
        payload["importance"] = merged["importance"]

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.post(
            f"/me/todo/lists/{list_id}/tasks",
            headers=_graph_headers(access_token),
            json=payload,
        )
        r.raise_for_status()
        task = r.json()

    log.info("microsoft_todo.create_task", list_id=list_id, task_id=task.get("id"))
    return {"task": task, "task_id": task.get("id")}


@register_node("microsoft_todo.list_tasks")
async def microsoft_todo_list_tasks(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List tasks in a Microsoft To Do task list.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      list_id      — task list ID to retrieve tasks from (required)
      top          — maximum number of tasks to return (optional)
      filter       — OData filter expression (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    list_id = merged.get("list_id")
    if not list_id:
        raise ValueError("list_id is required for microsoft_todo.list_tasks")

    params: dict = {}
    if merged.get("top"):
        params["$top"] = merged["top"]
    if merged.get("filter"):
        params["$filter"] = merged["filter"]

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.get(
            f"/me/todo/lists/{list_id}/tasks",
            headers=_graph_headers(access_token),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    tasks = data.get("value", [])
    log.info("microsoft_todo.list_tasks", list_id=list_id, count=len(tasks))
    return {"tasks": tasks, "count": len(tasks)}


@register_node("microsoft_todo.update_task")
async def microsoft_todo_update_task(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update an existing task in Microsoft To Do.

    config/input_data:
      access_token       — Microsoft Graph OAuth2 bearer token (required)
      list_id            — task list ID containing the task (required)
      task_id            — task ID to update (required)
      title              — new task title (optional)
      body               — new task body/notes (optional)
      due_date_time      — new due date/time in ISO 8601 format (optional)
      importance         — task importance: "low", "normal", or "high" (optional)
      status             — task status: "notStarted", "inProgress", "completed", etc. (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    list_id = merged.get("list_id")
    task_id = merged.get("task_id")
    if not list_id:
        raise ValueError("list_id is required for microsoft_todo.update_task")
    if not task_id:
        raise ValueError("task_id is required for microsoft_todo.update_task")

    payload: dict = {}
    if merged.get("title"):
        payload["title"] = merged["title"]
    if merged.get("body") is not None:
        payload["body"] = {"content": merged["body"], "contentType": "text"}
    if merged.get("due_date_time"):
        payload["dueDateTime"] = {"dateTime": merged["due_date_time"], "timeZone": "UTC"}
    if merged.get("importance"):
        payload["importance"] = merged["importance"]
    if merged.get("status"):
        payload["status"] = merged["status"]

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.patch(
            f"/me/todo/lists/{list_id}/tasks/{task_id}",
            headers=_graph_headers(access_token),
            json=payload,
        )
        r.raise_for_status()
        task = r.json()

    log.info("microsoft_todo.update_task", list_id=list_id, task_id=task_id)
    return {"task": task, "task_id": task_id}


@register_node("microsoft_todo.delete_task")
async def microsoft_todo_delete_task(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete a task from Microsoft To Do.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      list_id      — task list ID containing the task (required)
      task_id      — task ID to delete (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    list_id = merged.get("list_id")
    task_id = merged.get("task_id")
    if not list_id:
        raise ValueError("list_id is required for microsoft_todo.delete_task")
    if not task_id:
        raise ValueError("task_id is required for microsoft_todo.delete_task")

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.delete(
            f"/me/todo/lists/{list_id}/tasks/{task_id}",
            headers=_graph_headers(access_token),
        )
        r.raise_for_status()

    log.info("microsoft_todo.delete_task", list_id=list_id, task_id=task_id)
    return {"deleted": True, "task_id": task_id}


@register_node("microsoft_todo.complete_task")
async def microsoft_todo_complete_task(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Mark a Microsoft To Do task as completed.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      list_id      — task list ID containing the task (required)
      task_id      — task ID to complete (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    list_id = merged.get("list_id")
    task_id = merged.get("task_id")
    if not list_id:
        raise ValueError("list_id is required for microsoft_todo.complete_task")
    if not task_id:
        raise ValueError("task_id is required for microsoft_todo.complete_task")

    payload = {"status": "completed"}

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.patch(
            f"/me/todo/lists/{list_id}/tasks/{task_id}",
            headers=_graph_headers(access_token),
            json=payload,
        )
        r.raise_for_status()
        task = r.json()

    log.info("microsoft_todo.complete_task", list_id=list_id, task_id=task_id)
    return {"task": task, "task_id": task_id, "status": "completed"}
