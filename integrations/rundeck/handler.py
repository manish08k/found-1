"""Rundeck integration — job scheduling and execution management.

Credential fields:
  - url        : Rundeck base URL (e.g. https://rundeck.example.com)
  - auth_token : Rundeck API token

Auth: Bearer token via X-Rundeck-Auth-Token header
Base URL: {url}/api/41/

Nodes:
  - rundeck.list_projects   : list all available projects
  - rundeck.list_jobs       : list jobs in a project
  - rundeck.run_job         : execute a job
  - rundeck.get_execution   : get status/details of an execution
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

API_VERSION = 41


# ---------------------------------------------------------------------------
# Client helper
# ---------------------------------------------------------------------------

async def _client(credential_id: str, db) -> tuple[httpx.AsyncClient, str]:
    """Return (AsyncClient, base_url) configured with Rundeck auth."""
    creds = await get_credential_data(credential_id, db)
    url = creds.get("url", "").rstrip("/")
    auth_token = creds.get("auth_token")
    if not url:
        raise ValueError("Rundeck credential is missing 'url'")
    if not auth_token:
        raise ValueError("Rundeck credential is missing 'auth_token'")

    base_url = f"{url}/api/{API_VERSION}"
    client = httpx.AsyncClient(
        base_url=base_url,
        headers={
            "X-Rundeck-Auth-Token": auth_token,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )
    return client, base_url


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@register_node("rundeck.list_projects")
async def list_projects(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all Rundeck projects."""
    log.info("rundeck.list_projects")
    async with (await _client(credential_id, db))[0] as client:
        r = await client.get("/projects")
        r.raise_for_status()
        projects = r.json()
    log.info("rundeck.list_projects.done", count=len(projects))
    return {"projects": projects, "count": len(projects)}


@register_node("rundeck.list_jobs")
async def list_jobs(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List jobs within a Rundeck project."""
    project = config.get("project") or input_data.get("project")
    if not project:
        raise ValueError("'project' is required")

    group_path = config.get("group_path") or input_data.get("group_path")
    job_filter = config.get("job_filter") or input_data.get("job_filter")

    params = {}
    if group_path:
        params["groupPath"] = group_path
    if job_filter:
        params["jobFilter"] = job_filter

    log.info("rundeck.list_jobs", project=project)
    client, _ = await _client(credential_id, db)
    async with client:
        r = await client.get(f"/project/{project}/jobs", params=params)
        r.raise_for_status()
        jobs = r.json()
    log.info("rundeck.list_jobs.done", project=project, count=len(jobs))
    return {"jobs": jobs, "count": len(jobs), "project": project}


@register_node("rundeck.run_job")
async def run_job(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Execute a Rundeck job by ID."""
    job_id = config.get("job_id") or input_data.get("job_id")
    if not job_id:
        raise ValueError("'job_id' is required")

    options = config.get("options") or input_data.get("options", {})
    node_filter = config.get("node_filter") or input_data.get("node_filter")
    run_as_user = config.get("run_as_user") or input_data.get("run_as_user")

    payload: dict = {}
    if options:
        payload["options"] = options
    if node_filter:
        payload["filter"] = node_filter
    if run_as_user:
        payload["asUser"] = run_as_user

    log.info("rundeck.run_job", job_id=job_id)
    client, _ = await _client(credential_id, db)
    async with client:
        r = await client.post(f"/job/{job_id}/run", json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("rundeck.run_job.done", job_id=job_id, execution_id=data.get("id"))
    return {
        "execution_id": data.get("id"),
        "status": data.get("status"),
        "permalink": data.get("permalink"),
        "job": data.get("job", {}),
    }


@register_node("rundeck.get_execution")
async def get_execution(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve the status and details of a Rundeck execution."""
    execution_id = config.get("execution_id") or input_data.get("execution_id")
    if not execution_id:
        raise ValueError("'execution_id' is required")

    log.info("rundeck.get_execution", execution_id=execution_id)
    client, _ = await _client(credential_id, db)
    async with client:
        r = await client.get(f"/execution/{execution_id}")
        r.raise_for_status()
        data = r.json()
    log.info("rundeck.get_execution.done", execution_id=execution_id, status=data.get("status"))
    return {
        "execution_id": data.get("id"),
        "status": data.get("status"),
        "date_started": data.get("date-started", {}).get("date"),
        "date_ended": data.get("date-ended", {}).get("date"),
        "job": data.get("job", {}),
        "permalink": data.get("permalink"),
        "raw": data,
    }
