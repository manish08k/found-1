"""
ClickUp project management integration.

Credential fields:
  - api_key: ClickUp API key

Auth: Authorization header
Base URL: https://api.clickup.com/api/v2
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.clickup.com/api/v2"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("ClickUp credential is missing 'api_key'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "Authorization": api_key,
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
        raise ValueError(f"ClickUp API error {r.status_code}: {detail}")
    if not r.content:
        return {}
    return r.json()


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@register_node("clickup.create_task")
async def clickup_create_task(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /list/{list_id}/task — create a task in a list."""
    list_id = config.get("list_id") or input_data.get("list_id")
    name = config.get("name") or input_data.get("name")
    if not list_id:
        raise ValueError("clickup.create_task requires 'list_id'")
    if not name:
        raise ValueError("clickup.create_task requires 'name'")
    body: dict = {"name": name}
    for field in ("description", "status", "priority", "due_date", "assignees", "tags"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/list/{list_id}/task", json=body)
    return _check(r)


@register_node("clickup.get_task")
async def clickup_get_task(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /task/{task_id} — get a task by ID."""
    task_id = config.get("task_id") or input_data.get("task_id")
    if not task_id:
        raise ValueError("clickup.get_task requires 'task_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/task/{task_id}")
    return _check(r)


@register_node("clickup.update_task")
async def clickup_update_task(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /task/{task_id} — update a task."""
    task_id = config.get("task_id") or input_data.get("task_id")
    if not task_id:
        raise ValueError("clickup.update_task requires 'task_id'")
    body: dict = {}
    for field in ("name", "description", "status", "priority", "due_date", "assignees"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.put(f"/task/{task_id}", json=body)
    return _check(r)


@register_node("clickup.delete_task")
async def clickup_delete_task(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /task/{task_id} — delete a task."""
    task_id = config.get("task_id") or input_data.get("task_id")
    if not task_id:
        raise ValueError("clickup.delete_task requires 'task_id'")
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/task/{task_id}")
    return _check(r)


@register_node("clickup.list_tasks")
async def clickup_list_tasks(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /list/{list_id}/task — list tasks in a list."""
    list_id = config.get("list_id") or input_data.get("list_id")
    if not list_id:
        raise ValueError("clickup.list_tasks requires 'list_id'")
    params = {}
    for field in ("archived", "page", "order_by", "reverse", "subtasks", "statuses", "assignees"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            params[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/list/{list_id}/task", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------

@register_node("clickup.get_list")
async def clickup_get_list(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /list/{list_id} — get a list by ID."""
    list_id = config.get("list_id") or input_data.get("list_id")
    if not list_id:
        raise ValueError("clickup.get_list requires 'list_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/list/{list_id}")
    return _check(r)


@register_node("clickup.list_lists")
async def clickup_list_lists(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /folder/{folder_id}/list — list all lists in a folder."""
    folder_id = config.get("folder_id") or input_data.get("folder_id")
    if not folder_id:
        raise ValueError("clickup.list_lists requires 'folder_id'")
    params = {}
    archived = config.get("archived") or input_data.get("archived")
    if archived is not None:
        params["archived"] = archived
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/folder/{folder_id}/list", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Folders
# ---------------------------------------------------------------------------

@register_node("clickup.create_folder")
async def clickup_create_folder(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /space/{space_id}/folder — create a folder in a space."""
    space_id = config.get("space_id") or input_data.get("space_id")
    name = config.get("name") or input_data.get("name")
    if not space_id:
        raise ValueError("clickup.create_folder requires 'space_id'")
    if not name:
        raise ValueError("clickup.create_folder requires 'name'")
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/space/{space_id}/folder", json={"name": name})
    return _check(r)


@register_node("clickup.list_folders")
async def clickup_list_folders(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /space/{space_id}/folder — list folders in a space."""
    space_id = config.get("space_id") or input_data.get("space_id")
    if not space_id:
        raise ValueError("clickup.list_folders requires 'space_id'")
    params = {}
    archived = config.get("archived") or input_data.get("archived")
    if archived is not None:
        params["archived"] = archived
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/space/{space_id}/folder", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Spaces
# ---------------------------------------------------------------------------

@register_node("clickup.get_space")
async def clickup_get_space(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /space/{space_id} — get a space by ID."""
    space_id = config.get("space_id") or input_data.get("space_id")
    if not space_id:
        raise ValueError("clickup.get_space requires 'space_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/space/{space_id}")
    return _check(r)


@register_node("clickup.list_spaces")
async def clickup_list_spaces(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /team/{team_id}/space — list all spaces in a team/workspace."""
    team_id = config.get("team_id") or input_data.get("team_id")
    if not team_id:
        raise ValueError("clickup.list_spaces requires 'team_id'")
    params = {}
    archived = config.get("archived") or input_data.get("archived")
    if archived is not None:
        params["archived"] = archived
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/team/{team_id}/space", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Checklists & Comments
# ---------------------------------------------------------------------------

@register_node("clickup.create_checklist")
async def clickup_create_checklist(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /task/{task_id}/checklist — create a checklist on a task."""
    task_id = config.get("task_id") or input_data.get("task_id")
    name = config.get("name") or input_data.get("name")
    if not task_id:
        raise ValueError("clickup.create_checklist requires 'task_id'")
    if not name:
        raise ValueError("clickup.create_checklist requires 'name'")
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/task/{task_id}/checklist", json={"name": name})
    return _check(r)


@register_node("clickup.add_task_comment")
async def clickup_add_task_comment(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /task/{task_id}/comment — add a comment to a task."""
    task_id = config.get("task_id") or input_data.get("task_id")
    comment_text = config.get("comment_text") or input_data.get("comment_text")
    if not task_id:
        raise ValueError("clickup.add_task_comment requires 'task_id'")
    if not comment_text:
        raise ValueError("clickup.add_task_comment requires 'comment_text'")
    body: dict = {"comment_text": comment_text}
    assignee = config.get("assignee") or input_data.get("assignee")
    if assignee is not None:
        body["assignee"] = assignee
    notify_all = config.get("notify_all")
    if notify_all is None:
        notify_all = input_data.get("notify_all")
    if notify_all is not None:
        body["notify_all"] = bool(notify_all)
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/task/{task_id}/comment", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(creds: dict) -> dict:
    """Test ClickUp connection by fetching authorized teams."""
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Missing 'api_key'")
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        headers={"Authorization": api_key, "Content-Type": "application/json"},
        timeout=30.0,
    ) as client:
        r = await client.get("/team")
    if not r.is_success:
        raise ValueError(f"ClickUp connection failed: {r.status_code} {r.text}")
    return {"ok": True, "teams": r.json().get("teams", [])}
