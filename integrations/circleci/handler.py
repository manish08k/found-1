"""
CircleCI CI/CD integration.

Credential fields:
  - api_token: CircleCI personal API token

Auth: Circle-Token header
Base URL: https://circleci.com/api/v2
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

CIRCLECI_BASE_URL = "https://circleci.com/api/v2"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_token = creds.get("api_token")
    if not api_token:
        raise ValueError("CircleCI credential is missing 'api_token'")
    return httpx.AsyncClient(
        base_url=CIRCLECI_BASE_URL,
        headers={
            "Circle-Token": api_token,
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
        raise ValueError(f"CircleCI API error {r.status_code}: {detail}")
    try:
        return r.json()
    except Exception:
        return {"status": "ok", "text": r.text}


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

@register_node("circleci.get_user")
async def circleci_get_user(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /me — get the current authenticated user."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/me")
    return _check(r)


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

@register_node("circleci.list_projects")
async def circleci_list_projects(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /projects — list projects followed by the current user."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/projects")
    return _check(r)


# ---------------------------------------------------------------------------
# Pipelines
# ---------------------------------------------------------------------------

@register_node("circleci.list_pipelines")
async def circleci_list_pipelines(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /pipeline — list pipelines for a project or org slug."""
    params = {}
    org_slug = config.get("org_slug") or input_data.get("org_slug")
    if org_slug:
        params["org-slug"] = org_slug
    project_slug = config.get("project_slug") or input_data.get("project_slug")
    if project_slug:
        params["project-slug"] = project_slug
    page_token = config.get("page_token") or input_data.get("page_token")
    if page_token:
        params["page-token"] = page_token
    async with await _client(credential_id, db) as client:
        r = await client.get("/pipeline", params=params)
    return _check(r)


@register_node("circleci.get_pipeline")
async def circleci_get_pipeline(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /pipeline/{pipeline_id} — get a specific pipeline by ID."""
    pipeline_id = config.get("pipeline_id") or input_data.get("pipeline_id")
    if not pipeline_id:
        raise ValueError("circleci.get_pipeline requires 'pipeline_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/pipeline/{pipeline_id}")
    return _check(r)


@register_node("circleci.trigger_pipeline")
async def circleci_trigger_pipeline(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /project/{project_slug}/pipeline — trigger a new pipeline."""
    project_slug = config.get("project_slug") or input_data.get("project_slug")
    if not project_slug:
        raise ValueError("circleci.trigger_pipeline requires 'project_slug'")
    body: dict = {}
    branch = config.get("branch") or input_data.get("branch")
    if branch:
        body["branch"] = branch
    tag = config.get("tag") or input_data.get("tag")
    if tag:
        body["tag"] = tag
    parameters = config.get("parameters") or input_data.get("parameters")
    if parameters:
        body["parameters"] = parameters
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/project/{project_slug}/pipeline", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------

@register_node("circleci.list_workflows")
async def circleci_list_workflows(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /pipeline/{pipeline_id}/workflow — list workflows for a pipeline."""
    pipeline_id = config.get("pipeline_id") or input_data.get("pipeline_id")
    if not pipeline_id:
        raise ValueError("circleci.list_workflows requires 'pipeline_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/pipeline/{pipeline_id}/workflow")
    return _check(r)


@register_node("circleci.get_workflow")
async def circleci_get_workflow(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /workflow/{workflow_id} — get a specific workflow by ID."""
    workflow_id = config.get("workflow_id") or input_data.get("workflow_id")
    if not workflow_id:
        raise ValueError("circleci.get_workflow requires 'workflow_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/workflow/{workflow_id}")
    return _check(r)


@register_node("circleci.cancel_workflow")
async def circleci_cancel_workflow(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /workflow/{workflow_id}/cancel — cancel a running workflow."""
    workflow_id = config.get("workflow_id") or input_data.get("workflow_id")
    if not workflow_id:
        raise ValueError("circleci.cancel_workflow requires 'workflow_id'")
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/workflow/{workflow_id}/cancel")
    return _check(r)


@register_node("circleci.rerun_workflow")
async def circleci_rerun_workflow(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /workflow/{workflow_id}/rerun — rerun a workflow from failed or from beginning."""
    workflow_id = config.get("workflow_id") or input_data.get("workflow_id")
    if not workflow_id:
        raise ValueError("circleci.rerun_workflow requires 'workflow_id'")
    body: dict = {}
    from_failed = config.get("from_failed")
    if from_failed is None:
        from_failed = input_data.get("from_failed")
    if from_failed is not None:
        body["from_failed"] = bool(from_failed)
    jobs = config.get("jobs") or input_data.get("jobs")
    if jobs:
        body["jobs"] = jobs
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/workflow/{workflow_id}/rerun", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

@register_node("circleci.list_jobs")
async def circleci_list_jobs(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /workflow/{workflow_id}/job — list jobs for a workflow."""
    workflow_id = config.get("workflow_id") or input_data.get("workflow_id")
    if not workflow_id:
        raise ValueError("circleci.list_jobs requires 'workflow_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/workflow/{workflow_id}/job")
    return _check(r)


@register_node("circleci.get_job")
async def circleci_get_job(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /project/{project_slug}/job/{job_number} — get a specific job."""
    project_slug = config.get("project_slug") or input_data.get("project_slug")
    job_number = config.get("job_number") or input_data.get("job_number")
    if not project_slug or not job_number:
        raise ValueError("circleci.get_job requires 'project_slug' and 'job_number'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/project/{project_slug}/job/{job_number}")
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(credential_id: str, db) -> dict:
    """Test CircleCI connection by fetching the current user."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/me")
    _check(r)
    data = r.json()
    return {"ok": True, "login": data.get("login", data.get("name", "unknown"))}
