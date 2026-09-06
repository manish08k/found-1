"""Ashby ATS integration for recruiting and candidate management."""
import base64
import httpx
import structlog

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.ashbyhq.com"


def _get_headers(api_key: str) -> dict:
    token = base64.b64encode(f"{api_key}:".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
    }


@register_node("ashby.list_jobs")
async def ashby_list_jobs(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all job postings in Ashby."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("ashby requires 'api_key'")

    params = {}
    if merged.get("status"):
        params["status"] = merged["status"]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/job.list", headers=_get_headers(api_key), params=params)
        r.raise_for_status()
        return r.json()


@register_node("ashby.get_job")
async def ashby_get_job(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details of a specific job posting."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    api_key = creds.get("api_key")
    job_id = merged.get("job_id")
    if not job_id:
        raise ValueError("get_job requires 'job_id'")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}/job.info",
            headers=_get_headers(api_key),
            json={"jobId": job_id},
        )
        r.raise_for_status()
        return r.json()


@register_node("ashby.list_candidates")
async def ashby_list_candidates(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List candidates in Ashby."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    api_key = creds.get("api_key")

    payload = {}
    if merged.get("cursor"):
        payload["cursor"] = merged["cursor"]
    if merged.get("limit"):
        payload["limit"] = int(merged["limit"])

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}/candidate.list",
            headers=_get_headers(api_key),
            json=payload,
        )
        r.raise_for_status()
        return r.json()


@register_node("ashby.create_candidate")
async def ashby_create_candidate(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new candidate in Ashby."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    api_key = creds.get("api_key")
    name = merged.get("name")
    if not name:
        raise ValueError("create_candidate requires 'name'")

    payload = {"name": name}
    for field in ["email", "phoneNumber", "linkedInUrl", "githubUrl", "website", "alternateEmail"]:
        if merged.get(field):
            payload[field] = merged[field]
    if merged.get("social_links"):
        payload["socialLinks"] = merged["social_links"]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}/candidate.create",
            headers=_get_headers(api_key),
            json=payload,
        )
        r.raise_for_status()
        return r.json()


@register_node("ashby.list_applications")
async def ashby_list_applications(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List applications with optional filters."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    api_key = creds.get("api_key")

    payload = {}
    if merged.get("cursor"):
        payload["cursor"] = merged["cursor"]
    if merged.get("limit"):
        payload["limit"] = int(merged["limit"])
    if merged.get("job_id"):
        payload["jobId"] = merged["job_id"]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}/application.list",
            headers=_get_headers(api_key),
            json=payload,
        )
        r.raise_for_status()
        return r.json()


@register_node("ashby.add_note")
async def ashby_add_note(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Add a note to a candidate's profile."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    api_key = creds.get("api_key")
    candidate_id = merged.get("candidate_id")
    note = merged.get("note") or merged.get("content")
    if not candidate_id or not note:
        raise ValueError("add_note requires 'candidate_id' and 'note'")

    payload = {"candidateId": candidate_id, "note": note}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}/candidate.createNote",
            headers=_get_headers(api_key),
            json=payload,
        )
        r.raise_for_status()
        return r.json()
