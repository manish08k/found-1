"""Greenhouse integration — jobs, candidates, applications, and offers."""
import base64
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

GREENHOUSE_BASE = "https://harvest.greenhouse.io/v1"


def _greenhouse_headers(api_key: str) -> dict:
    token = base64.b64encode(f"{api_key}:".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


@register_node("greenhouse.list_jobs")
async def greenhouse_list_jobs(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """List all jobs in the Greenhouse account.

    config:
      api_key — Greenhouse Harvest API key (required)
      status  — filter by status: "open", "closed", or "draft" (optional)
      per_page — results per page, max 500 (optional, default 100)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")

    params: dict = {"per_page": merged.get("per_page", 100)}
    if merged.get("status"):
        params["status"] = merged["status"]

    async with httpx.AsyncClient(base_url=GREENHOUSE_BASE, timeout=30) as client:
        r = await client.get("/jobs", headers=_greenhouse_headers(api_key), params=params)
        r.raise_for_status()
        jobs = r.json()

    log.info("greenhouse.list_jobs", count=len(jobs))
    return {"jobs": jobs, "count": len(jobs)}


@register_node("greenhouse.list_candidates")
async def greenhouse_list_candidates(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """List candidates in the Greenhouse account.

    config:
      api_key     — Greenhouse Harvest API key (required)
      per_page    — results per page, max 500 (optional, default 100)
      updated_after — ISO 8601 date to filter by last update (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")

    params: dict = {"per_page": merged.get("per_page", 100)}
    if merged.get("updated_after"):
        params["updated_after"] = merged["updated_after"]

    async with httpx.AsyncClient(base_url=GREENHOUSE_BASE, timeout=30) as client:
        r = await client.get(
            "/candidates", headers=_greenhouse_headers(api_key), params=params
        )
        r.raise_for_status()
        candidates = r.json()

    log.info("greenhouse.list_candidates", count=len(candidates))
    return {"candidates": candidates, "count": len(candidates)}


@register_node("greenhouse.get_candidate")
async def greenhouse_get_candidate(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Get details of a specific Greenhouse candidate.

    config:
      api_key      — Greenhouse Harvest API key (required)
      candidate_id — candidate ID (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    candidate_id = merged.get("candidate_id")
    if not candidate_id:
        raise ValueError("candidate_id is required for greenhouse.get_candidate")

    async with httpx.AsyncClient(base_url=GREENHOUSE_BASE, timeout=30) as client:
        r = await client.get(
            f"/candidates/{candidate_id}", headers=_greenhouse_headers(api_key)
        )
        r.raise_for_status()
        candidate = r.json()

    log.info("greenhouse.get_candidate", candidate_id=candidate_id)
    return {"candidate": candidate, "candidate_id": candidate_id}


@register_node("greenhouse.add_application")
async def greenhouse_add_application(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Add an application to a job for a candidate.

    config:
      api_key      — Greenhouse Harvest API key (required)
      on_behalf_of — user ID of the recruiter on whose behalf to act (required)
      candidate_id — candidate ID (required)
      job_id       — job ID to apply to (required)
      source_id    — source ID (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    on_behalf_of = merged.get("on_behalf_of")
    candidate_id = merged.get("candidate_id")
    job_id = merged.get("job_id")

    if not candidate_id or not job_id or not on_behalf_of:
        raise ValueError(
            "candidate_id, job_id, and on_behalf_of are required for greenhouse.add_application"
        )

    headers = _greenhouse_headers(api_key)
    headers["On-Behalf-Of"] = str(on_behalf_of)

    payload: dict = {"job_id": job_id}
    if merged.get("source_id"):
        payload["source_id"] = merged["source_id"]

    async with httpx.AsyncClient(base_url=GREENHOUSE_BASE, timeout=30) as client:
        r = await client.post(
            f"/candidates/{candidate_id}/applications",
            headers=headers,
            json=payload,
        )
        r.raise_for_status()
        application = r.json()

    log.info(
        "greenhouse.add_application",
        candidate_id=candidate_id,
        job_id=job_id,
        application_id=application.get("id"),
    )
    return {"application": application, "application_id": application.get("id")}


@register_node("greenhouse.list_applications")
async def greenhouse_list_applications(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """List applications in the Greenhouse account.

    config:
      api_key      — Greenhouse Harvest API key (required)
      job_id       — filter by job ID (optional)
      candidate_id — filter by candidate ID (optional)
      status       — filter by status: "active", "rejected", "hired" (optional)
      per_page     — results per page, max 500 (optional, default 100)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")

    params: dict = {"per_page": merged.get("per_page", 100)}
    for key in ("job_id", "candidate_id", "status"):
        if merged.get(key):
            params[key] = merged[key]

    async with httpx.AsyncClient(base_url=GREENHOUSE_BASE, timeout=30) as client:
        r = await client.get(
            "/applications", headers=_greenhouse_headers(api_key), params=params
        )
        r.raise_for_status()
        applications = r.json()

    log.info("greenhouse.list_applications", count=len(applications))
    return {"applications": applications, "count": len(applications)}


@register_node("greenhouse.list_offers")
async def greenhouse_list_offers(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """List offers for a specific application.

    config:
      api_key         — Greenhouse Harvest API key (required)
      application_id  — application ID to list offers for (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    application_id = merged.get("application_id")
    if not application_id:
        raise ValueError("application_id is required for greenhouse.list_offers")

    async with httpx.AsyncClient(base_url=GREENHOUSE_BASE, timeout=30) as client:
        r = await client.get(
            f"/applications/{application_id}/offers",
            headers=_greenhouse_headers(api_key),
        )
        r.raise_for_status()
        offers = r.json()

    log.info(
        "greenhouse.list_offers",
        application_id=application_id,
        count=len(offers) if isinstance(offers, list) else 1,
    )
    return {"offers": offers, "application_id": application_id}
