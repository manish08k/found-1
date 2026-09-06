"""
Workable applicant tracking system integration.

Credential fields:
  - api_key: Workable API access token
  - subdomain: Workable account subdomain (e.g. 'yourcompany')

Auth: Bearer token via Authorization header
Base URL: https://{subdomain}.workable.com/spi/v3
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
        raise ValueError("Workable credential missing 'api_key'")
    if not subdomain:
        raise ValueError("Workable credential missing 'subdomain'")
    return httpx.AsyncClient(
        base_url=f"https://{subdomain}.workable.com/spi/v3",
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
        raise ValueError(f"Workable API error {r.status_code}: {detail}")
    try:
        return r.json()
    except Exception:
        return {"status": "ok"}


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

@register_node("workable.list_jobs")
async def workable_list_jobs(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /jobs — list all jobs."""
    params = {}
    state = config.get("state") or input_data.get("state")
    if state:
        params["state"] = state
    limit = config.get("limit") or input_data.get("limit")
    if limit:
        params["limit"] = int(limit)
    async with await _client(credential_id, db) as client:
        r = await client.get("/jobs", params=params)
    return _check(r)


@register_node("workable.get_job")
async def workable_get_job(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /jobs/{shortcode} — get a specific job."""
    shortcode = config.get("shortcode") or input_data.get("shortcode")
    if not shortcode:
        raise ValueError("workable.get_job requires 'shortcode'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/jobs/{shortcode}")
    return _check(r)


@register_node("workable.create_job")
async def workable_create_job(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /jobs — create a new job."""
    title = config.get("title") or input_data.get("title")
    if not title:
        raise ValueError("workable.create_job requires 'title'")
    body: dict = {"title": title}
    for field in ("department", "description", "requirements", "benefits",
                  "employment_type", "location", "salary"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/jobs", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------

@register_node("workable.list_candidates")
async def workable_list_candidates(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /candidates — list all candidates."""
    params = {}
    stage = config.get("stage") or input_data.get("stage")
    if stage:
        params["stage"] = stage
    limit = config.get("limit") or input_data.get("limit")
    if limit:
        params["limit"] = int(limit)
    async with await _client(credential_id, db) as client:
        r = await client.get("/candidates", params=params)
    return _check(r)


@register_node("workable.get_candidate")
async def workable_get_candidate(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /candidates/{id} — get a specific candidate."""
    candidate_id = config.get("candidate_id") or input_data.get("candidate_id")
    if not candidate_id:
        raise ValueError("workable.get_candidate requires 'candidate_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/candidates/{candidate_id}")
    return _check(r)


@register_node("workable.create_candidate")
async def workable_create_candidate(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /jobs/{shortcode}/candidates — create a candidate for a job."""
    shortcode = config.get("shortcode") or input_data.get("shortcode")
    if not shortcode:
        raise ValueError("workable.create_candidate requires 'shortcode'")
    body: dict = {}
    for field in ("name", "firstname", "lastname", "email", "phone",
                  "headline", "summary", "address", "source"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/jobs/{shortcode}/candidates", json={"candidate": body})
    return _check(r)


@register_node("workable.move_candidate")
async def workable_move_candidate(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /candidates/{id}/move — move candidate to a different stage."""
    candidate_id = config.get("candidate_id") or input_data.get("candidate_id")
    stage = config.get("stage") or input_data.get("stage")
    if not candidate_id or not stage:
        raise ValueError("workable.move_candidate requires 'candidate_id' and 'stage'")
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/candidates/{candidate_id}/move", json={"stage": stage})
    return _check(r)


@register_node("workable.add_candidate_comment")
async def workable_add_candidate_comment(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /candidates/{id}/comments — add a comment on a candidate."""
    candidate_id = config.get("candidate_id") or input_data.get("candidate_id")
    body_text = config.get("body") or input_data.get("body")
    if not candidate_id or not body_text:
        raise ValueError("workable.add_candidate_comment requires 'candidate_id' and 'body'")
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/candidates/{candidate_id}/comments",
                               json={"body": body_text})
    return _check(r)


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------

@register_node("workable.list_members")
async def workable_list_members(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /members — list all team members."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/members")
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(credential_id: str, db) -> dict:
    """Test Workable connection by listing jobs."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/jobs", params={"limit": 1})
    _check(r)
    return {"ok": True, "message": "Workable connection successful"}
