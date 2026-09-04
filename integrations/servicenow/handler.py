"""
ServiceNow integration.

Credential fields:
  - instance: e.g. dev12345.service-now.com
  - username: ServiceNow username
  - password: ServiceNow password

Auth: HTTP Basic
Base URL: https://{instance}/api/now
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    instance = creds.get("instance", "").rstrip("/")
    username = creds.get("username")
    password = creds.get("password")
    if not instance:
        raise ValueError("ServiceNow credential is missing 'instance'")
    if not username:
        raise ValueError("ServiceNow credential is missing 'username'")
    if not password:
        raise ValueError("ServiceNow credential is missing 'password'")
    base_url = f"https://{instance}/api/now"
    return httpx.AsyncClient(
        base_url=base_url,
        auth=(username, password),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"ServiceNow API error {r.status_code}: {detail}")
    return r.json()


async def test_connection(credential_id: str, db) -> dict:
    """Verify credentials by fetching current user info."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/table/sys_user", params={"sysparm_limit": 1})
    return _check(r)


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------

@register_node("servicenow.list_incidents")
async def servicenow_list_incidents(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /table/incident — list incidents."""
    params: dict = {}
    limit = config.get("sysparm_limit") or input_data.get("sysparm_limit")
    if limit:
        params["sysparm_limit"] = int(limit)
    query = config.get("sysparm_query") or input_data.get("sysparm_query")
    if query:
        params["sysparm_query"] = query
    fields = config.get("sysparm_fields") or input_data.get("sysparm_fields")
    if fields:
        params["sysparm_fields"] = fields
    async with await _client(credential_id, db) as client:
        r = await client.get("/table/incident", params=params)
    return _check(r)


@register_node("servicenow.get_incident")
async def servicenow_get_incident(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /table/incident/{sys_id} — get an incident by sys_id."""
    sys_id = config.get("sys_id") or input_data.get("sys_id")
    if not sys_id:
        raise ValueError("servicenow.get_incident requires 'sys_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/table/incident/{sys_id}")
    return _check(r)


@register_node("servicenow.create_incident")
async def servicenow_create_incident(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /table/incident — create a new incident."""
    short_description = config.get("short_description") or input_data.get("short_description")
    if not short_description:
        raise ValueError("servicenow.create_incident requires 'short_description'")
    body: dict = {"short_description": short_description}
    for field in ("description", "urgency", "impact", "priority", "category", "assignment_group", "caller_id"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/table/incident", json=body)
    return _check(r)


@register_node("servicenow.update_incident")
async def servicenow_update_incident(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PATCH /table/incident/{sys_id} — update an incident."""
    sys_id = config.get("sys_id") or input_data.get("sys_id")
    if not sys_id:
        raise ValueError("servicenow.update_incident requires 'sys_id'")
    body: dict = {}
    for field in ("short_description", "description", "state", "urgency", "impact", "priority",
                  "resolution_notes", "close_code", "assignment_group"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.patch(f"/table/incident/{sys_id}", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Change Requests
# ---------------------------------------------------------------------------

@register_node("servicenow.list_change_requests")
async def servicenow_list_change_requests(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /table/change_request — list change requests."""
    params: dict = {}
    limit = config.get("sysparm_limit") or input_data.get("sysparm_limit")
    if limit:
        params["sysparm_limit"] = int(limit)
    query = config.get("sysparm_query") or input_data.get("sysparm_query")
    if query:
        params["sysparm_query"] = query
    async with await _client(credential_id, db) as client:
        r = await client.get("/table/change_request", params=params)
    return _check(r)


@register_node("servicenow.create_change_request")
async def servicenow_create_change_request(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /table/change_request — create a change request."""
    short_description = config.get("short_description") or input_data.get("short_description")
    if not short_description:
        raise ValueError("servicenow.create_change_request requires 'short_description'")
    body: dict = {"short_description": short_description}
    for field in ("description", "type", "risk", "impact", "assignment_group", "start_date", "end_date"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/table/change_request", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@register_node("servicenow.list_users")
async def servicenow_list_users(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /table/sys_user — list users."""
    params: dict = {}
    limit = config.get("sysparm_limit") or input_data.get("sysparm_limit")
    if limit:
        params["sysparm_limit"] = int(limit)
    query = config.get("sysparm_query") or input_data.get("sysparm_query")
    if query:
        params["sysparm_query"] = query
    async with await _client(credential_id, db) as client:
        r = await client.get("/table/sys_user", params=params)
    return _check(r)


@register_node("servicenow.get_user")
async def servicenow_get_user(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /table/sys_user/{sys_id} — get a user by sys_id."""
    sys_id = config.get("sys_id") or input_data.get("sys_id")
    if not sys_id:
        raise ValueError("servicenow.get_user requires 'sys_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/table/sys_user/{sys_id}")
    return _check(r)


# ---------------------------------------------------------------------------
# CMDB (Configuration Items)
# ---------------------------------------------------------------------------

@register_node("servicenow.list_cmdb_items")
async def servicenow_list_cmdb_items(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /table/cmdb_ci — list configuration items."""
    params: dict = {}
    limit = config.get("sysparm_limit") or input_data.get("sysparm_limit")
    if limit:
        params["sysparm_limit"] = int(limit)
    query = config.get("sysparm_query") or input_data.get("sysparm_query")
    if query:
        params["sysparm_query"] = query
    ci_class = config.get("ci_class") or input_data.get("ci_class", "cmdb_ci")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/table/{ci_class}", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Service Catalog
# ---------------------------------------------------------------------------

@register_node("servicenow.list_catalog_items")
async def servicenow_list_catalog_items(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /sn_sc/servicecatalog/items — list service catalog items."""
    params: dict = {}
    limit = config.get("sysparm_limit") or input_data.get("sysparm_limit")
    if limit:
        params["sysparm_limit"] = int(limit)
    async with await _client(credential_id, db) as client:
        r = await client.get("/sn_sc/servicecatalog/items", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Generic Table Operations
# ---------------------------------------------------------------------------

@register_node("servicenow.query_table")
async def servicenow_query_table(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /table/{table_name} — query any ServiceNow table."""
    table_name = config.get("table_name") or input_data.get("table_name")
    if not table_name:
        raise ValueError("servicenow.query_table requires 'table_name'")
    params: dict = {}
    limit = config.get("sysparm_limit") or input_data.get("sysparm_limit")
    if limit:
        params["sysparm_limit"] = int(limit)
    query = config.get("sysparm_query") or input_data.get("sysparm_query")
    if query:
        params["sysparm_query"] = query
    fields = config.get("sysparm_fields") or input_data.get("sysparm_fields")
    if fields:
        params["sysparm_fields"] = fields
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/table/{table_name}", params=params)
    return _check(r)


@register_node("servicenow.create_record")
async def servicenow_create_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /table/{table_name} — create a record in any ServiceNow table."""
    table_name = config.get("table_name") or input_data.get("table_name")
    if not table_name:
        raise ValueError("servicenow.create_record requires 'table_name'")
    data = config.get("data") or input_data.get("data")
    if not data:
        raise ValueError("servicenow.create_record requires 'data' dict with record fields")
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/table/{table_name}", json=data)
    return _check(r)
