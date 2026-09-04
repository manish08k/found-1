"""
Clockify time-tracking integration.

Credential fields:
  - api_key: Clockify API key

Auth: X-Api-Key header
Base URL: https://api.clockify.me/api/v1
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.clockify.me/api/v1"
REPORTS_URL = "https://reports.api.clockify.me/v1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Clockify credential is missing 'api_key'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "X-Api-Key": api_key,
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
        raise ValueError(f"Clockify API error {r.status_code}: {detail}")
    if not r.content:
        return {}
    return r.json()


# ---------------------------------------------------------------------------
# User & Workspaces
# ---------------------------------------------------------------------------

@register_node("clockify.get_user")
async def clockify_get_user(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /user — get current user info."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/user")
    return _check(r)


@register_node("clockify.list_workspaces")
async def clockify_list_workspaces(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /workspaces — list all workspaces."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/workspaces")
    return _check(r)


# ---------------------------------------------------------------------------
# Time Entries
# ---------------------------------------------------------------------------

@register_node("clockify.list_time_entries")
async def clockify_list_time_entries(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /workspaces/{workspace_id}/user/{user_id}/time-entries — list time entries."""
    workspace_id = config.get("workspace_id") or input_data.get("workspace_id")
    user_id = config.get("user_id") or input_data.get("user_id")
    if not workspace_id:
        raise ValueError("clockify.list_time_entries requires 'workspace_id'")
    if not user_id:
        raise ValueError("clockify.list_time_entries requires 'user_id'")
    params = {}
    for field in ("start", "end", "project", "task", "tags", "page", "page-size"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            params[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/workspaces/{workspace_id}/user/{user_id}/time-entries", params=params)
    return _check(r)


@register_node("clockify.create_time_entry")
async def clockify_create_time_entry(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /workspaces/{workspace_id}/time-entries — create a time entry."""
    workspace_id = config.get("workspace_id") or input_data.get("workspace_id")
    start = config.get("start") or input_data.get("start")
    if not workspace_id:
        raise ValueError("clockify.create_time_entry requires 'workspace_id'")
    if not start:
        raise ValueError("clockify.create_time_entry requires 'start' (ISO datetime)")
    body: dict = {"start": start}
    for field in ("end", "billable", "description", "projectId", "taskId", "tagIds"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/workspaces/{workspace_id}/time-entries", json=body)
    return _check(r)


@register_node("clockify.update_time_entry")
async def clockify_update_time_entry(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /workspaces/{workspace_id}/time-entries/{time_entry_id} — update a time entry."""
    workspace_id = config.get("workspace_id") or input_data.get("workspace_id")
    time_entry_id = config.get("time_entry_id") or input_data.get("time_entry_id")
    start = config.get("start") or input_data.get("start")
    if not workspace_id:
        raise ValueError("clockify.update_time_entry requires 'workspace_id'")
    if not time_entry_id:
        raise ValueError("clockify.update_time_entry requires 'time_entry_id'")
    if not start:
        raise ValueError("clockify.update_time_entry requires 'start'")
    body: dict = {"start": start}
    for field in ("end", "billable", "description", "projectId", "taskId", "tagIds"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.put(f"/workspaces/{workspace_id}/time-entries/{time_entry_id}", json=body)
    return _check(r)


@register_node("clockify.delete_time_entry")
async def clockify_delete_time_entry(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /workspaces/{workspace_id}/time-entries/{time_entry_id} — delete a time entry."""
    workspace_id = config.get("workspace_id") or input_data.get("workspace_id")
    time_entry_id = config.get("time_entry_id") or input_data.get("time_entry_id")
    if not workspace_id:
        raise ValueError("clockify.delete_time_entry requires 'workspace_id'")
    if not time_entry_id:
        raise ValueError("clockify.delete_time_entry requires 'time_entry_id'")
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/workspaces/{workspace_id}/time-entries/{time_entry_id}")
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Clockify API error {r.status_code}: {detail}")
    return {"ok": True, "time_entry_id": time_entry_id}


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

@register_node("clockify.list_projects")
async def clockify_list_projects(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /workspaces/{workspace_id}/projects — list projects."""
    workspace_id = config.get("workspace_id") or input_data.get("workspace_id")
    if not workspace_id:
        raise ValueError("clockify.list_projects requires 'workspace_id'")
    params = {}
    for field in ("archived", "page", "page-size", "name"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            params[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/workspaces/{workspace_id}/projects", params=params)
    return _check(r)


@register_node("clockify.create_project")
async def clockify_create_project(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /workspaces/{workspace_id}/projects — create a project."""
    workspace_id = config.get("workspace_id") or input_data.get("workspace_id")
    name = config.get("name") or input_data.get("name")
    if not workspace_id:
        raise ValueError("clockify.create_project requires 'workspace_id'")
    if not name:
        raise ValueError("clockify.create_project requires 'name'")
    body: dict = {"name": name}
    for field in ("clientId", "billable", "color", "isPublic", "note"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/workspaces/{workspace_id}/projects", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------

@register_node("clockify.list_clients")
async def clockify_list_clients(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /workspaces/{workspace_id}/clients — list clients."""
    workspace_id = config.get("workspace_id") or input_data.get("workspace_id")
    if not workspace_id:
        raise ValueError("clockify.list_clients requires 'workspace_id'")
    params = {}
    name = config.get("name") or input_data.get("name")
    if name:
        params["name"] = name
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/workspaces/{workspace_id}/clients", params=params)
    return _check(r)


@register_node("clockify.create_client")
async def clockify_create_client(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /workspaces/{workspace_id}/clients — create a client."""
    workspace_id = config.get("workspace_id") or input_data.get("workspace_id")
    name = config.get("name") or input_data.get("name")
    if not workspace_id:
        raise ValueError("clockify.create_client requires 'workspace_id'")
    if not name:
        raise ValueError("clockify.create_client requires 'name'")
    body: dict = {"name": name}
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/workspaces/{workspace_id}/clients", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Tags & Reports
# ---------------------------------------------------------------------------

@register_node("clockify.list_tags")
async def clockify_list_tags(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /workspaces/{workspace_id}/tags — list tags."""
    workspace_id = config.get("workspace_id") or input_data.get("workspace_id")
    if not workspace_id:
        raise ValueError("clockify.list_tags requires 'workspace_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/workspaces/{workspace_id}/tags")
    return _check(r)


@register_node("clockify.list_reports_summary")
async def clockify_list_reports_summary(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /workspaces/{workspace_id}/reports/summary — get summary reports."""
    from oauth.flow import get_credential_data as _get_creds
    workspace_id = config.get("workspace_id") or input_data.get("workspace_id")
    date_range_start = config.get("date_range_start") or input_data.get("date_range_start")
    date_range_end = config.get("date_range_end") or input_data.get("date_range_end")
    if not workspace_id:
        raise ValueError("clockify.list_reports_summary requires 'workspace_id'")
    if not date_range_start or not date_range_end:
        raise ValueError("clockify.list_reports_summary requires 'date_range_start' and 'date_range_end'")
    creds = await _get_creds(credential_id, db)
    api_key = creds.get("api_key")
    body: dict = {
        "dateRangeStart": date_range_start,
        "dateRangeEnd": date_range_end,
        "summaryFilter": config.get("summaryFilter") or input_data.get("summaryFilter") or {"groups": ["USER"]},
    }
    async with httpx.AsyncClient(
        base_url=REPORTS_URL,
        headers={"X-Api-Key": api_key, "Content-Type": "application/json"},
        timeout=30.0,
    ) as client:
        r = await client.post(f"/workspaces/{workspace_id}/reports/summary", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(creds: dict) -> dict:
    """Test Clockify connection by fetching current user."""
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Missing 'api_key'")
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        headers={"X-Api-Key": api_key, "Content-Type": "application/json"},
        timeout=30.0,
    ) as client:
        r = await client.get("/user")
    if not r.is_success:
        raise ValueError(f"Clockify connection failed: {r.status_code} {r.text}")
    data = r.json()
    return {"ok": True, "email": data.get("email"), "id": data.get("id")}
