"""Formspark integration — form management and submission handling."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

FORMSPARK_BASE = "https://api.formspark.io/v1"


def _formspark_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@register_node("formspark.list_forms")
async def formspark_list_forms(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all forms in the Formspark workspace.

    config:
      token — Formspark API token (required)
    """
    merged = {**config, **input_data}
    token = merged.get("token", "")

    async with httpx.AsyncClient(base_url=FORMSPARK_BASE, timeout=30) as client:
        r = await client.get("/forms", headers=_formspark_headers(token))
        r.raise_for_status()
        data = r.json()

    forms = data.get("forms", data) if isinstance(data, dict) else data
    log.info("formspark.list_forms", count=len(forms))
    return {"forms": forms, "count": len(forms)}


@register_node("formspark.get_submissions")
async def formspark_get_submissions(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get submissions for a specific Formspark form.

    config:
      token   — Formspark API token (required)
      form_id — form ID to fetch submissions for (required)
      page    — page number for pagination (optional)
      limit   — results per page (optional)
    """
    merged = {**config, **input_data}
    token = merged.get("token", "")
    form_id = merged.get("form_id")
    if not form_id:
        raise ValueError("form_id is required for formspark.get_submissions")

    params = {}
    if merged.get("page") is not None:
        params["page"] = merged["page"]
    if merged.get("limit") is not None:
        params["limit"] = merged["limit"]

    async with httpx.AsyncClient(base_url=FORMSPARK_BASE, timeout=30) as client:
        r = await client.get(
            f"/forms/{form_id}/submissions",
            headers=_formspark_headers(token),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    submissions = data.get("submissions", data) if isinstance(data, dict) else data
    log.info("formspark.get_submissions", form_id=form_id, count=len(submissions))
    return {"submissions": submissions, "form_id": form_id, "count": len(submissions)}


@register_node("formspark.delete_submission")
async def formspark_delete_submission(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete a submission from a Formspark form.

    config:
      token         — Formspark API token (required)
      form_id       — form ID containing the submission (required)
      submission_id — submission ID to delete (required)
    """
    merged = {**config, **input_data}
    token = merged.get("token", "")
    form_id = merged.get("form_id")
    submission_id = merged.get("submission_id")
    if not form_id:
        raise ValueError("form_id is required for formspark.delete_submission")
    if not submission_id:
        raise ValueError("submission_id is required for formspark.delete_submission")

    async with httpx.AsyncClient(base_url=FORMSPARK_BASE, timeout=30) as client:
        r = await client.delete(
            f"/forms/{form_id}/submissions/{submission_id}",
            headers=_formspark_headers(token),
        )
        r.raise_for_status()

    log.info("formspark.delete_submission", form_id=form_id, submission_id=submission_id)
    return {"deleted": True, "submission_id": submission_id, "form_id": form_id}
