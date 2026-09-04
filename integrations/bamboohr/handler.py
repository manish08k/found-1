"""
BambooHR integration.

Credential fields:
  - api_key: BambooHR API key
  - subdomain: company subdomain (e.g. "mycompany")

Auth: HTTP Basic with api_key + "x"
Base URL: https://api.bamboohr.com/api/gateway.php/{subdomain}/v1
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    subdomain = creds.get("subdomain")
    if not api_key:
        raise ValueError("BambooHR credential is missing 'api_key'")
    if not subdomain:
        raise ValueError("BambooHR credential is missing 'subdomain'")
    base_url = f"https://api.bamboohr.com/api/gateway.php/{subdomain}/v1"
    return httpx.AsyncClient(
        base_url=base_url,
        auth=(api_key, "x"),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"BambooHR API error {r.status_code}: {detail}")
    try:
        return r.json()
    except Exception:
        return {"status": r.status_code, "text": r.text}


async def test_connection(credential_id: str, db) -> dict:
    """Verify credentials by fetching the employee directory."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/employees/directory")
    return _check(r)


# ---------------------------------------------------------------------------
# Employees
# ---------------------------------------------------------------------------

@register_node("bamboohr.list_employees")
async def bamboohr_list_employees(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /employees/directory — list all employees."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/employees/directory")
    return _check(r)


@register_node("bamboohr.get_employee")
async def bamboohr_get_employee(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /employees/{id} — get an employee by ID."""
    employee_id = config.get("employee_id") or input_data.get("employee_id")
    if not employee_id:
        raise ValueError("bamboohr.get_employee requires 'employee_id'")
    fields = config.get("fields") or input_data.get("fields", "all")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/employees/{employee_id}", params={"fields": fields})
    return _check(r)


@register_node("bamboohr.update_employee")
async def bamboohr_update_employee(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /employees/{id} — update employee fields."""
    employee_id = config.get("employee_id") or input_data.get("employee_id")
    if not employee_id:
        raise ValueError("bamboohr.update_employee requires 'employee_id'")
    fields: dict = {}
    for key in ("firstName", "lastName", "jobTitle", "department", "location", "workEmail", "mobilePhone"):
        v = config.get(key)
        if v is None:
            v = input_data.get(key)
        if v is not None:
            fields[key] = v
    if not fields:
        raise ValueError("bamboohr.update_employee requires at least one field to update")
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/employees/{employee_id}", json=fields)
    return _check(r)


# ---------------------------------------------------------------------------
# Time Off
# ---------------------------------------------------------------------------

@register_node("bamboohr.list_time_off_requests")
async def bamboohr_list_time_off_requests(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /time_off/requests/ — list time off requests."""
    params: dict = {}
    start = config.get("start") or input_data.get("start")
    if start:
        params["start"] = start
    end = config.get("end") or input_data.get("end")
    if end:
        params["end"] = end
    employee_id = config.get("employee_id") or input_data.get("employee_id")
    if employee_id:
        params["employeeId"] = employee_id
    status = config.get("status") or input_data.get("status")
    if status:
        params["status"] = status
    async with await _client(credential_id, db) as client:
        r = await client.get("/time_off/requests/", params=params)
    return _check(r)


@register_node("bamboohr.get_time_off_request")
async def bamboohr_get_time_off_request(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /time_off/requests/{id} — get a specific time off request."""
    request_id = config.get("request_id") or input_data.get("request_id")
    if not request_id:
        raise ValueError("bamboohr.get_time_off_request requires 'request_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/time_off/requests/{request_id}")
    return _check(r)


@register_node("bamboohr.create_time_off_request")
async def bamboohr_create_time_off_request(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /employees/{employee_id}/time_off/request — create a time off request."""
    employee_id = config.get("employee_id") or input_data.get("employee_id")
    start = config.get("start") or input_data.get("start")
    end = config.get("end") or input_data.get("end")
    time_off_type_id = config.get("time_off_type_id") or input_data.get("time_off_type_id")
    if not employee_id or not start or not end or not time_off_type_id:
        raise ValueError("bamboohr.create_time_off_request requires 'employee_id', 'start', 'end', 'time_off_type_id'")
    body: dict = {
        "status": "requested",
        "start": start,
        "end": end,
        "timeOffTypeId": time_off_type_id,
    }
    note = config.get("note") or input_data.get("note")
    if note:
        body["note"] = note
    async with await _client(credential_id, db) as client:
        r = await client.put(f"/employees/{employee_id}/time_off/request", json=body)
    return _check(r)


@register_node("bamboohr.approve_time_off")
async def bamboohr_approve_time_off(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /time_off/requests/{id}/status — approve or deny a time off request."""
    request_id = config.get("request_id") or input_data.get("request_id")
    status = config.get("status") or input_data.get("status", "approved")
    if not request_id:
        raise ValueError("bamboohr.approve_time_off requires 'request_id'")
    body: dict = {"status": status}
    note = config.get("note") or input_data.get("note")
    if note:
        body["note"] = note
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/time_off/requests/{request_id}/status", json=body)
    return _check(r)


@register_node("bamboohr.list_time_off_types")
async def bamboohr_list_time_off_types(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /time_off/types/ — list available time off types."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/time_off/types/")
    return _check(r)


# ---------------------------------------------------------------------------
# Employee Files
# ---------------------------------------------------------------------------

@register_node("bamboohr.get_employee_files")
async def bamboohr_get_employee_files(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /employees/{id}/files/view/ — get employee file list."""
    employee_id = config.get("employee_id") or input_data.get("employee_id")
    if not employee_id:
        raise ValueError("bamboohr.get_employee_files requires 'employee_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/employees/{employee_id}/files/view/")
    return _check(r)


@register_node("bamboohr.upload_employee_file")
async def bamboohr_upload_employee_file(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /employees/{id}/files — upload a file for an employee."""
    employee_id = config.get("employee_id") or input_data.get("employee_id")
    filename = config.get("filename") or input_data.get("filename")
    file_content = config.get("file_content") or input_data.get("file_content")
    category_id = config.get("category_id") or input_data.get("category_id", "0")
    if not employee_id or not filename or file_content is None:
        raise ValueError("bamboohr.upload_employee_file requires 'employee_id', 'filename', and 'file_content'")
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    subdomain = creds.get("subdomain")
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"https://api.bamboohr.com/api/gateway.php/{subdomain}/v1/employees/{employee_id}/files",
            auth=(api_key, "x"),
            files={"file": (filename, file_content)},
            data={"category": category_id, "fileName": filename},
        )
    return _check(r)


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

@register_node("bamboohr.list_job_openings")
async def bamboohr_list_job_openings(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /applicant_tracking/jobs — list job openings."""
    params = {}
    status_groups = config.get("statusGroups") or input_data.get("statusGroups")
    if status_groups:
        params["statusGroups"] = status_groups
    async with await _client(credential_id, db) as client:
        r = await client.get("/applicant_tracking/jobs", params=params)
    return _check(r)
