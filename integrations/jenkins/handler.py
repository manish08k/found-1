"""
Jenkins CI/CD integration via REST API.

Credential fields:
  - base_url: Jenkins server URL (e.g. https://jenkins.example.com)
  - username: Jenkins username
  - api_token: Jenkins API token

Auth: HTTP Basic with username:api_token
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    base_url = creds.get("base_url", "").rstrip("/")
    username = creds.get("username")
    api_token = creds.get("api_token")
    if not base_url:
        raise ValueError("Jenkins credential is missing 'base_url'")
    if not username:
        raise ValueError("Jenkins credential is missing 'username'")
    if not api_token:
        raise ValueError("Jenkins credential is missing 'api_token'")
    return httpx.AsyncClient(
        base_url=base_url,
        auth=(username, api_token),
        headers={"Content-Type": "application/json"},
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Jenkins API error {r.status_code}: {detail}")
    try:
        return r.json()
    except Exception:
        return {"status": "ok", "text": r.text}


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

@register_node("jenkins.list_jobs")
async def jenkins_list_jobs(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /api/json — list all top-level jobs."""
    params = {"tree": "jobs[name,url,color,description]"}
    async with await _client(credential_id, db) as client:
        r = await client.get("/api/json", params=params)
    return _check(r)


@register_node("jenkins.get_job")
async def jenkins_get_job(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /job/{job_name}/api/json — get details for a specific job."""
    job_name = config.get("job_name") or input_data.get("job_name")
    if not job_name:
        raise ValueError("jenkins.get_job requires 'job_name'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/job/{job_name}/api/json")
    return _check(r)


@register_node("jenkins.build_job")
async def jenkins_build_job(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /job/{job_name}/build — trigger a build for a job."""
    job_name = config.get("job_name") or input_data.get("job_name")
    if not job_name:
        raise ValueError("jenkins.build_job requires 'job_name'")
    parameters = config.get("parameters") or input_data.get("parameters")
    async with await _client(credential_id, db) as client:
        if parameters:
            form_data = {"json": str({"parameter": [{"name": k, "value": v} for k, v in parameters.items()]})}
            r = await client.post(f"/job/{job_name}/buildWithParameters", data=form_data)
        else:
            r = await client.post(f"/job/{job_name}/build")
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Jenkins API error {r.status_code}: {detail}")
    location = r.headers.get("Location", "")
    return {"triggered": True, "job_name": job_name, "queue_url": location}


# ---------------------------------------------------------------------------
# Builds
# ---------------------------------------------------------------------------

@register_node("jenkins.get_build")
async def jenkins_get_build(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /job/{job_name}/{build_number}/api/json — get build details."""
    job_name = config.get("job_name") or input_data.get("job_name")
    build_number = config.get("build_number") or input_data.get("build_number")
    if not job_name or not build_number:
        raise ValueError("jenkins.get_build requires 'job_name' and 'build_number'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/job/{job_name}/{build_number}/api/json")
    return _check(r)


@register_node("jenkins.list_builds")
async def jenkins_list_builds(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /job/{job_name}/api/json — list builds for a job."""
    job_name = config.get("job_name") or input_data.get("job_name")
    if not job_name:
        raise ValueError("jenkins.list_builds requires 'job_name'")
    params = {"tree": "builds[number,url,result,timestamp,duration,displayName]"}
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/job/{job_name}/api/json", params=params)
    return _check(r)


@register_node("jenkins.cancel_build")
async def jenkins_cancel_build(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /job/{job_name}/{build_number}/stop — cancel/stop a running build."""
    job_name = config.get("job_name") or input_data.get("job_name")
    build_number = config.get("build_number") or input_data.get("build_number")
    if not job_name or not build_number:
        raise ValueError("jenkins.cancel_build requires 'job_name' and 'build_number'")
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/job/{job_name}/{build_number}/stop")
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Jenkins API error {r.status_code}: {detail}")
    return {"cancelled": True, "job_name": job_name, "build_number": build_number}


@register_node("jenkins.get_build_log")
async def jenkins_get_build_log(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /job/{job_name}/{build_number}/consoleText — get build console log."""
    job_name = config.get("job_name") or input_data.get("job_name")
    build_number = config.get("build_number") or input_data.get("build_number")
    if not job_name or not build_number:
        raise ValueError("jenkins.get_build_log requires 'job_name' and 'build_number'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/job/{job_name}/{build_number}/consoleText")
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Jenkins API error {r.status_code}: {detail}")
    return {"job_name": job_name, "build_number": build_number, "log": r.text}


# ---------------------------------------------------------------------------
# Nodes (Agents)
# ---------------------------------------------------------------------------

@register_node("jenkins.list_nodes")
async def jenkins_list_nodes(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /computer/api/json — list all Jenkins nodes/agents."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/computer/api/json")
    return _check(r)


# ---------------------------------------------------------------------------
# Queue
# ---------------------------------------------------------------------------

@register_node("jenkins.get_queue")
async def jenkins_get_queue(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /queue/api/json — get the build queue."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/queue/api/json")
    return _check(r)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@register_node("jenkins.list_views")
async def jenkins_list_views(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /api/json — list all views."""
    params = {"tree": "views[name,url,description]"}
    async with await _client(credential_id, db) as client:
        r = await client.get("/api/json", params=params)
    return _check(r)


@register_node("jenkins.create_view")
async def jenkins_create_view(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /createView — create a new Jenkins view."""
    view_name = config.get("name") or input_data.get("name")
    if not view_name:
        raise ValueError("jenkins.create_view requires 'name'")
    view_type = config.get("type") or input_data.get("type") or "hudson.model.ListView"
    async with await _client(credential_id, db) as client:
        r = await client.post(
            "/createView",
            params={"name": view_name},
            json={"name": view_name, "mode": view_type, "stapler-class": view_type},
        )
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Jenkins API error {r.status_code}: {detail}")
    return {"created": True, "name": view_name}


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(credential_id: str, db) -> dict:
    """Test Jenkins connection by fetching server info."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/api/json", params={"tree": "nodeName,url"})
    _check(r)
    data = r.json()
    return {"ok": True, "node_name": data.get("nodeName", "master"), "url": data.get("url", "")}
