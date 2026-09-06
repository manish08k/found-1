"""Paperform integration — form management and submission handling."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

PAPERFORM_BASE = "https://api.paperform.co/v1"


def _paperform_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@register_node("paperform.list_forms")
async def paperform_list_forms(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all forms in the Paperform account.

    config:
      token  — Paperform API token (required)
      search — search term to filter forms (optional)
      limit  — max forms to return (optional)
      page   — page number (optional)
    """
    merged = {**config, **input_data}
    token = merged.get("token", "")

    params = {}
    if merged.get("search"):
        params["search"] = merged["search"]
    if merged.get("limit") is not None:
        params["limit"] = merged["limit"]
    if merged.get("page") is not None:
        params["page"] = merged["page"]

    async with httpx.AsyncClient(base_url=PAPERFORM_BASE, timeout=30) as client:
        r = await client.get("/forms", headers=_paperform_headers(token), params=params)
        r.raise_for_status()
        data = r.json()

    forms = data.get("results", data) if isinstance(data, dict) else data
    log.info("paperform.list_forms", count=len(forms))
    return {"forms": forms, "count": len(forms)}


@register_node("paperform.get_submissions")
async def paperform_get_submissions(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get submissions for a specific Paperform form.

    config:
      token   — Paperform API token (required)
      form_id — form ID or slug to fetch submissions for (required)
      limit   — max submissions to return (optional)
      page    — page number (optional)
      after   — filter submissions after this date (optional)
      before  — filter submissions before this date (optional)
    """
    merged = {**config, **input_data}
    token = merged.get("token", "")
    form_id = merged.get("form_id")
    if not form_id:
        raise ValueError("form_id is required for paperform.get_submissions")

    params = {}
    if merged.get("limit") is not None:
        params["limit"] = merged["limit"]
    if merged.get("page") is not None:
        params["page"] = merged["page"]
    if merged.get("after"):
        params["after"] = merged["after"]
    if merged.get("before"):
        params["before"] = merged["before"]

    async with httpx.AsyncClient(base_url=PAPERFORM_BASE, timeout=30) as client:
        r = await client.get(
            f"/forms/{form_id}/submissions",
            headers=_paperform_headers(token),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    submissions = data.get("results", data) if isinstance(data, dict) else data
    total = data.get("total_results") if isinstance(data, dict) else len(submissions)
    log.info("paperform.get_submissions", form_id=form_id, count=len(submissions))
    return {"submissions": submissions, "form_id": form_id, "count": len(submissions), "total": total}


@register_node("paperform.delete_submission")
async def paperform_delete_submission(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete a submission from a Paperform form.

    config:
      token         — Paperform API token (required)
      form_id       — form ID containing the submission (required)
      submission_id — submission ID to delete (required)
    """
    merged = {**config, **input_data}
    token = merged.get("token", "")
    form_id = merged.get("form_id")
    submission_id = merged.get("submission_id")
    if not form_id:
        raise ValueError("form_id is required for paperform.delete_submission")
    if not submission_id:
        raise ValueError("submission_id is required for paperform.delete_submission")

    async with httpx.AsyncClient(base_url=PAPERFORM_BASE, timeout=30) as client:
        r = await client.delete(
            f"/forms/{form_id}/submissions/{submission_id}",
            headers=_paperform_headers(token),
        )
        r.raise_for_status()

    log.info("paperform.delete_submission", form_id=form_id, submission_id=submission_id)
    return {"deleted": True, "submission_id": submission_id, "form_id": form_id}
