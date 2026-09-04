"""
Todoist task management integration.

Credential fields:
  - api_key: Todoist API key

Auth: Authorization: Bearer {api_key}
Base URL: https://api.todoist.com/rest/v2
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.todoist.com/rest/v2"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Todoist credential is missing 'api_key'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Todoist API error {r.status_code}: {detail}")
    if not r.content:
        return {}
    return r.json()


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@register_node("todoist.create_task")
async def todoist_create_task(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /tasks — create a new task."""
    content = config.get("content") or input_data.get("content")
    if not content:
        raise ValueError("todoist.create_task requires 'content'")
    body: dict = {"content": content}
    for field in ("description", "project_id", "section_id", "parent_id", "order",
                  "labels", "priority", "due_string", "due_date", "due_datetime",
                  "assignee_id"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/tasks", json=body)
    return _check(r)


@register_node("todoist.get_task")
async def todoist_get_task(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /tasks/{task_id} — get a task by ID."""
    task_id = config.get("task_id") or input_data.get("task_id")
    if not task_id:
        raise ValueError("todoist.get_task requires 'task_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/tasks/{task_id}")
    return _check(r)


@register_node("todoist.update_task")
async def todoist_update_task(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /tasks/{task_id} — update a task."""
    task_id = config.get("task_id") or input_data.get("task_id")
    if not task_id:
        raise ValueError("todoist.update_task requires 'task_id'")
    body: dict = {}
    for field in ("content", "description", "labels", "priority", "due_string",
                  "due_date", "due_datetime", "assignee_id"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/tasks/{task_id}", json=body)
    return _check(r)


@register_node("todoist.close_task")
async def todoist_close_task(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /tasks/{task_id}/close — close (complete) a task."""
    task_id = config.get("task_id") or input_data.get("task_id")
    if not task_id:
        raise ValueError("todoist.close_task requires 'task_id'")
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/tasks/{task_id}/close")
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Todoist API error {r.status_code}: {detail}")
    return {"ok": True, "task_id": task_id}


@register_node("todoist.delete_task")
async def todoist_delete_task(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /tasks/{task_id} — delete a task."""
    task_id = config.get("task_id") or input_data.get("task_id")
    if not task_id:
        raise ValueError("todoist.delete_task requires 'task_id'")
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/tasks/{task_id}")
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Todoist API error {r.status_code}: {detail}")
    return {"ok": True, "task_id": task_id}


@register_node("todoist.list_tasks")
async def todoist_list_tasks(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /tasks — list active tasks with optional filters."""
    params = {}
    for field in ("project_id", "section_id", "label", "filter", "lang", "ids"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            params[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/tasks", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

@register_node("todoist.create_project")
async def todoist_create_project(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /projects — create a new project."""
    name = config.get("name") or input_data.get("name")
    if not name:
        raise ValueError("todoist.create_project requires 'name'")
    body: dict = {"name": name}
    for field in ("parent_id", "color", "is_favorite", "view_style"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/projects", json=body)
    return _check(r)


@register_node("todoist.get_project")
async def todoist_get_project(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /projects/{project_id} — get a project by ID."""
    project_id = config.get("project_id") or input_data.get("project_id")
    if not project_id:
        raise ValueError("todoist.get_project requires 'project_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/projects/{project_id}")
    return _check(r)


@register_node("todoist.list_projects")
async def todoist_list_projects(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /projects — list all projects."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/projects")
    return _check(r)


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

@register_node("todoist.create_section")
async def todoist_create_section(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /sections — create a new section in a project."""
    name = config.get("name") or input_data.get("name")
    project_id = config.get("project_id") or input_data.get("project_id")
    if not name:
        raise ValueError("todoist.create_section requires 'name'")
    if not project_id:
        raise ValueError("todoist.create_section requires 'project_id'")
    body: dict = {"name": name, "project_id": project_id}
    order = config.get("order")
    if order is None:
        order = input_data.get("order")
    if order is not None:
        body["order"] = order
    async with await _client(credential_id, db) as client:
        r = await client.post("/sections", json=body)
    return _check(r)


@register_node("todoist.list_sections")
async def todoist_list_sections(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /sections — list sections, optionally filtered by project."""
    params = {}
    project_id = config.get("project_id") or input_data.get("project_id")
    if project_id:
        params["project_id"] = project_id
    async with await _client(credential_id, db) as client:
        r = await client.get("/sections", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Comments & Labels
# ---------------------------------------------------------------------------

@register_node("todoist.add_comment")
async def todoist_add_comment(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /comments — add a comment to a task or project."""
    content = config.get("content") or input_data.get("content")
    if not content:
        raise ValueError("todoist.add_comment requires 'content'")
    body: dict = {"content": content}
    task_id = config.get("task_id") or input_data.get("task_id")
    project_id = config.get("project_id") or input_data.get("project_id")
    if task_id:
        body["task_id"] = task_id
    elif project_id:
        body["project_id"] = project_id
    else:
        raise ValueError("todoist.add_comment requires either 'task_id' or 'project_id'")
    attachment = config.get("attachment") or input_data.get("attachment")
    if attachment:
        body["attachment"] = attachment
    async with await _client(credential_id, db) as client:
        r = await client.post("/comments", json=body)
    return _check(r)


@register_node("todoist.list_labels")
async def todoist_list_labels(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /labels — list all personal labels."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/labels")
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(creds: dict) -> dict:
    """Test Todoist connection by fetching current user projects."""
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Missing 'api_key'")
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=30.0,
    ) as client:
        r = await client.get("/projects")
    if not r.is_success:
        raise ValueError(f"Todoist connection failed: {r.status_code} {r.text}")
    return {"ok": True, "projects_count": len(r.json())}
