"""
Harvest time-tracking and invoicing integration.

Credential fields:
  - access_token: Harvest personal access token
  - account_id: Harvest account ID

Auth: Authorization: Bearer {access_token}, Harvest-Account-Id: {account_id}
Base URL: https://api.harvestapp.com/v2
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.harvestapp.com/v2"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    access_token = creds.get("access_token")
    account_id = creds.get("account_id")
    if not access_token:
        raise ValueError("Harvest credential is missing 'access_token'")
    if not account_id:
        raise ValueError("Harvest credential is missing 'account_id'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Harvest-Account-Id": str(account_id),
            "User-Agent": "Automation Platform",
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
        raise ValueError(f"Harvest API error {r.status_code}: {detail}")
    if not r.content:
        return {}
    return r.json()


# ---------------------------------------------------------------------------
# Time Entries
# ---------------------------------------------------------------------------

@register_node("harvest.list_time_entries")
async def harvest_list_time_entries(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /time_entries — list time entries."""
    params = {}
    for field in ("user_id", "client_id", "project_id", "task_id", "from", "to",
                  "is_billed", "is_running", "page", "per_page"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            params[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/time_entries", params=params)
    return _check(r)


@register_node("harvest.create_time_entry")
async def harvest_create_time_entry(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /time_entries — create a time entry."""
    project_id = config.get("project_id") or input_data.get("project_id")
    task_id = config.get("task_id") or input_data.get("task_id")
    spent_date = config.get("spent_date") or input_data.get("spent_date")
    if not project_id:
        raise ValueError("harvest.create_time_entry requires 'project_id'")
    if not task_id:
        raise ValueError("harvest.create_time_entry requires 'task_id'")
    if not spent_date:
        raise ValueError("harvest.create_time_entry requires 'spent_date' (YYYY-MM-DD)")
    body: dict = {
        "project_id": project_id,
        "task_id": task_id,
        "spent_date": spent_date,
    }
    for field in ("hours", "notes", "user_id", "started_time", "ended_time"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/time_entries", json=body)
    return _check(r)


@register_node("harvest.update_time_entry")
async def harvest_update_time_entry(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PATCH /time_entries/{time_entry_id} — update a time entry."""
    time_entry_id = config.get("time_entry_id") or input_data.get("time_entry_id")
    if not time_entry_id:
        raise ValueError("harvest.update_time_entry requires 'time_entry_id'")
    body: dict = {}
    for field in ("project_id", "task_id", "spent_date", "hours", "notes",
                  "started_time", "ended_time"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.patch(f"/time_entries/{time_entry_id}", json=body)
    return _check(r)


@register_node("harvest.delete_time_entry")
async def harvest_delete_time_entry(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /time_entries/{time_entry_id} — delete a time entry."""
    time_entry_id = config.get("time_entry_id") or input_data.get("time_entry_id")
    if not time_entry_id:
        raise ValueError("harvest.delete_time_entry requires 'time_entry_id'")
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/time_entries/{time_entry_id}")
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Harvest API error {r.status_code}: {detail}")
    return {"ok": True, "time_entry_id": time_entry_id}


# ---------------------------------------------------------------------------
# Projects, Clients, Tasks
# ---------------------------------------------------------------------------

@register_node("harvest.list_projects")
async def harvest_list_projects(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /projects — list all projects."""
    params = {}
    for field in ("client_id", "is_active", "page", "per_page"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            params[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/projects", params=params)
    return _check(r)


@register_node("harvest.list_clients")
async def harvest_list_clients(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /clients — list all clients."""
    params = {}
    is_active = config.get("is_active")
    if is_active is None:
        is_active = input_data.get("is_active")
    if is_active is not None:
        params["is_active"] = is_active
    async with await _client(credential_id, db) as client:
        r = await client.get("/clients", params=params)
    return _check(r)


@register_node("harvest.list_tasks")
async def harvest_list_tasks(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /tasks — list all tasks."""
    params = {}
    is_active = config.get("is_active")
    if is_active is None:
        is_active = input_data.get("is_active")
    if is_active is not None:
        params["is_active"] = is_active
    async with await _client(credential_id, db) as client:
        r = await client.get("/tasks", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------

@register_node("harvest.list_invoices")
async def harvest_list_invoices(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /invoices — list invoices."""
    params = {}
    for field in ("client_id", "project_id", "updated_since", "from", "to",
                  "state", "page", "per_page"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            params[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/invoices", params=params)
    return _check(r)


@register_node("harvest.create_invoice")
async def harvest_create_invoice(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /invoices — create a new invoice."""
    client_id = config.get("client_id") or input_data.get("client_id")
    if not client_id:
        raise ValueError("harvest.create_invoice requires 'client_id'")
    body: dict = {"client_id": client_id}
    for field in ("retainer_id", "estimate_id", "number", "purchase_order",
                  "tax", "tax2", "discount", "subject", "notes", "currency",
                  "issue_date", "due_date", "payment_term", "line_items"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/invoices", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Estimates
# ---------------------------------------------------------------------------

@register_node("harvest.list_estimates")
async def harvest_list_estimates(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /estimates — list estimates."""
    params = {}
    for field in ("client_id", "updated_since", "from", "to", "state", "page", "per_page"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            params[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/estimates", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

@register_node("harvest.get_current_user")
async def harvest_get_current_user(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /users/me — get current authenticated user."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/users/me")
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(creds: dict) -> dict:
    """Test Harvest connection by fetching the current user."""
    access_token = creds.get("access_token")
    account_id = creds.get("account_id")
    if not access_token:
        raise ValueError("Missing 'access_token'")
    if not account_id:
        raise ValueError("Missing 'account_id'")
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Harvest-Account-Id": str(account_id),
            "User-Agent": "Automation Platform",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    ) as client:
        r = await client.get("/users/me")
    if not r.is_success:
        raise ValueError(f"Harvest connection failed: {r.status_code} {r.text}")
    data = r.json()
    return {"ok": True, "email": data.get("email"), "id": data.get("id")}
