"""
Toggl Track time-tracking integration.

Credential fields:
  - api_token: Toggl API token

Auth: HTTP Basic auth with api_token as username and "api_token" as password
Base URL: https://api.track.toggl.com/api/v9
"""
import base64
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.track.toggl.com/api/v9"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_token = creds.get("api_token")
    if not api_token:
        raise ValueError("Toggl credential is missing 'api_token'")
    raw = f"{api_token}:api_token"
    encoded = base64.b64encode(raw.encode()).decode()
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Basic {encoded}",
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
        raise ValueError(f"Toggl API error {r.status_code}: {detail}")
    if not r.content:
        return {}
    return r.json()


# ---------------------------------------------------------------------------
# Me / Workspaces
# ---------------------------------------------------------------------------

@register_node("toggl.get_me")
async def toggl_get_me(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /me — get current user profile."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/me")
    return _check(r)


@register_node("toggl.list_workspaces")
async def toggl_list_workspaces(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /workspaces — list all workspaces for the current user."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/workspaces")
    return _check(r)


# ---------------------------------------------------------------------------
# Time Entries
# ---------------------------------------------------------------------------

@register_node("toggl.list_time_entries")
async def toggl_list_time_entries(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /me/time_entries — list time entries."""
    params = {}
    for field in ("start_date", "end_date", "meta"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            params[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/me/time_entries", params=params)
    return _check(r)


@register_node("toggl.create_time_entry")
async def toggl_create_time_entry(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /workspaces/{workspace_id}/time_entries — create a time entry."""
    workspace_id = config.get("workspace_id") or input_data.get("workspace_id")
    if not workspace_id:
        raise ValueError("toggl.create_time_entry requires 'workspace_id'")
    start = config.get("start") or input_data.get("start")
    if not start:
        raise ValueError("toggl.create_time_entry requires 'start' (RFC3339 datetime)")
    created_with = config.get("created_with") or input_data.get("created_with") or "automation"
    body: dict = {
        "start": start,
        "created_with": created_with,
        "workspace_id": int(workspace_id),
    }
    for field in ("description", "project_id", "tag_ids", "billable", "duration",
                  "stop", "at", "tags"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/workspaces/{workspace_id}/time_entries", json=body)
    return _check(r)


@register_node("toggl.get_time_entry")
async def toggl_get_time_entry(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /me/time_entries/{time_entry_id} — get a time entry by ID."""
    time_entry_id = config.get("time_entry_id") or input_data.get("time_entry_id")
    if not time_entry_id:
        raise ValueError("toggl.get_time_entry requires 'time_entry_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/me/time_entries/{time_entry_id}")
    return _check(r)


@register_node("toggl.update_time_entry")
async def toggl_update_time_entry(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /workspaces/{workspace_id}/time_entries/{time_entry_id} — update a time entry."""
    workspace_id = config.get("workspace_id") or input_data.get("workspace_id")
    time_entry_id = config.get("time_entry_id") or input_data.get("time_entry_id")
    if not workspace_id:
        raise ValueError("toggl.update_time_entry requires 'workspace_id'")
    if not time_entry_id:
        raise ValueError("toggl.update_time_entry requires 'time_entry_id'")
    body: dict = {}
    for field in ("description", "start", "stop", "duration", "project_id",
                  "tag_ids", "billable", "tags"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.put(f"/workspaces/{workspace_id}/time_entries/{time_entry_id}", json=body)
    return _check(r)


@register_node("toggl.delete_time_entry")
async def toggl_delete_time_entry(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /workspaces/{workspace_id}/time_entries/{time_entry_id} — delete a time entry."""
    workspace_id = config.get("workspace_id") or input_data.get("workspace_id")
    time_entry_id = config.get("time_entry_id") or input_data.get("time_entry_id")
    if not workspace_id:
        raise ValueError("toggl.delete_time_entry requires 'workspace_id'")
    if not time_entry_id:
        raise ValueError("toggl.delete_time_entry requires 'time_entry_id'")
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/workspaces/{workspace_id}/time_entries/{time_entry_id}")
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Toggl API error {r.status_code}: {detail}")
    return {"ok": True, "time_entry_id": time_entry_id}


@register_node("toggl.start_timer")
async def toggl_start_timer(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /workspaces/{workspace_id}/time_entries — start a running timer (duration = -1)."""
    workspace_id = config.get("workspace_id") or input_data.get("workspace_id")
    if not workspace_id:
        raise ValueError("toggl.start_timer requires 'workspace_id'")
    import datetime
    start = config.get("start") or input_data.get("start") or datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    body: dict = {
        "start": start,
        "duration": -1,
        "created_with": "automation",
        "workspace_id": int(workspace_id),
    }
    description = config.get("description") or input_data.get("description")
    if description:
        body["description"] = description
    project_id = config.get("project_id") or input_data.get("project_id")
    if project_id:
        body["project_id"] = project_id
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/workspaces/{workspace_id}/time_entries", json=body)
    return _check(r)


@register_node("toggl.stop_timer")
async def toggl_stop_timer(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PATCH /workspaces/{workspace_id}/time_entries/{time_entry_id}/stop — stop the running timer."""
    workspace_id = config.get("workspace_id") or input_data.get("workspace_id")
    time_entry_id = config.get("time_entry_id") or input_data.get("time_entry_id")
    if not workspace_id:
        raise ValueError("toggl.stop_timer requires 'workspace_id'")
    if not time_entry_id:
        raise ValueError("toggl.stop_timer requires 'time_entry_id'")
    async with await _client(credential_id, db) as client:
        r = await client.patch(f"/workspaces/{workspace_id}/time_entries/{time_entry_id}/stop")
    return _check(r)


# ---------------------------------------------------------------------------
# Projects & Clients
# ---------------------------------------------------------------------------

@register_node("toggl.list_projects")
async def toggl_list_projects(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /workspaces/{workspace_id}/projects — list projects in a workspace."""
    workspace_id = config.get("workspace_id") or input_data.get("workspace_id")
    if not workspace_id:
        raise ValueError("toggl.list_projects requires 'workspace_id'")
    params = {}
    active = config.get("active")
    if active is None:
        active = input_data.get("active")
    if active is not None:
        params["active"] = active
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/workspaces/{workspace_id}/projects", params=params)
    return _check(r)


@register_node("toggl.create_project")
async def toggl_create_project(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /workspaces/{workspace_id}/projects — create a project."""
    workspace_id = config.get("workspace_id") or input_data.get("workspace_id")
    name = config.get("name") or input_data.get("name")
    if not workspace_id:
        raise ValueError("toggl.create_project requires 'workspace_id'")
    if not name:
        raise ValueError("toggl.create_project requires 'name'")
    body: dict = {"name": name, "workspace_id": int(workspace_id)}
    for field in ("client_id", "color", "billable", "is_private", "active"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/workspaces/{workspace_id}/projects", json=body)
    return _check(r)


@register_node("toggl.list_clients")
async def toggl_list_clients(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /workspaces/{workspace_id}/clients — list clients in a workspace."""
    workspace_id = config.get("workspace_id") or input_data.get("workspace_id")
    if not workspace_id:
        raise ValueError("toggl.list_clients requires 'workspace_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/workspaces/{workspace_id}/clients")
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(creds: dict) -> dict:
    """Test Toggl connection by fetching the current user profile."""
    api_token = creds.get("api_token")
    if not api_token:
        raise ValueError("Missing 'api_token'")
    raw = f"{api_token}:api_token"
    encoded = base64.b64encode(raw.encode()).decode()
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        headers={"Authorization": f"Basic {encoded}", "Content-Type": "application/json"},
        timeout=30.0,
    ) as client:
        r = await client.get("/me")
    if not r.is_success:
        raise ValueError(f"Toggl connection failed: {r.status_code} {r.text}")
    data = r.json()
    return {"ok": True, "email": data.get("email"), "id": data.get("id")}
