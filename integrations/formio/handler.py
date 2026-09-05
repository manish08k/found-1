"""
Form.io integration.

Provides form management and submission operations via the Form.io API.

Credential fields:
  - api_key    : Form.io API key (JWT or x-jwt-token)
  - base_url   : (optional) custom deployment URL, default https://api.form.io/

Auth: x-jwt-token header (Bearer also accepted by newer Form.io instances).
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

DEFAULT_BASE = "https://api.form.io"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    base_url = creds.get("base_url", DEFAULT_BASE).rstrip("/")
    if not api_key:
        raise ValueError("Form.io credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=base_url,
        headers={
            "x-jwt-token": api_key,
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 400:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise RuntimeError(f"Form.io API error {r.status_code}: {detail}")


@register_node("formio.list_forms")
async def list_forms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all forms in the Form.io project."""
    limit = int(config.get("limit", 25))
    skip = int(config.get("skip", 0))
    form_type = config.get("type", "form")  # "form" or "resource"
    tags = config.get("tags")  # comma-separated tag filter

    params: dict = {
        "limit": limit,
        "skip": skip,
        "type": form_type,
        "select": "title,name,path,type,tags,created,modified",
    }
    if tags:
        params["tags"] = tags

    log.info("formio.list_forms", limit=limit, skip=skip, type=form_type)

    async with await _client(credential_id, db) as client:
        r = await client.get("/form", params=params)
        _raise_for_status(r)
        forms = r.json()

    log.info("formio.list_forms.done", count=len(forms))
    return {"forms": forms, "count": len(forms)}


@register_node("formio.get_submissions")
async def get_submissions(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve submissions for a specific form."""
    form_path = (
        config.get("form_path")
        or input_data.get("form_path")
    )
    form_id = (
        config.get("form_id")
        or input_data.get("form_id")
    )
    if not form_path and not form_id:
        raise ValueError("'form_path' or 'form_id' is required")

    endpoint = f"/{form_path}/submission" if form_path else f"/form/{form_id}/submission"
    limit = int(config.get("limit", 25))
    skip = int(config.get("skip", 0))
    sort = config.get("sort", "-created")

    params: dict = {"limit": limit, "skip": skip, "sort": sort}

    # Optional field filters passed as query params
    filters = config.get("filters") or input_data.get("filters") or {}
    for key, val in filters.items():
        params[key] = val

    log.info("formio.get_submissions", endpoint=endpoint, limit=limit)

    async with await _client(credential_id, db) as client:
        r = await client.get(endpoint, params=params)
        _raise_for_status(r)
        submissions = r.json()
        total_header = r.headers.get("Content-Range", "")

    log.info("formio.get_submissions.done", count=len(submissions))
    return {
        "submissions": submissions,
        "count": len(submissions),
        "content_range": total_header,
    }


@register_node("formio.create_submission")
async def create_submission(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new submission on a Form.io form."""
    form_path = config.get("form_path") or input_data.get("form_path")
    form_id = config.get("form_id") or input_data.get("form_id")
    if not form_path and not form_id:
        raise ValueError("'form_path' or 'form_id' is required")

    endpoint = f"/{form_path}/submission" if form_path else f"/form/{form_id}/submission"

    # submission data lives under the 'data' key in Form.io
    submission_data = config.get("data") or input_data.get("data")
    if not submission_data:
        raise ValueError("'data' dict with form field values is required")

    body = {"data": submission_data}

    # Optional metadata
    metadata = config.get("metadata") or input_data.get("metadata")
    if metadata:
        body["metadata"] = metadata

    log.info("formio.create_submission", endpoint=endpoint, fields=list(submission_data.keys()))

    async with await _client(credential_id, db) as client:
        r = await client.post(endpoint, json=body)
        _raise_for_status(r)
        submission = r.json()

    log.info("formio.create_submission.done", submission_id=submission.get("_id"))
    return {"submission": submission, "submission_id": submission.get("_id")}


@register_node("formio.delete_submission")
async def delete_submission(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Delete a submission from a Form.io form."""
    form_path = config.get("form_path") or input_data.get("form_path")
    form_id = config.get("form_id") or input_data.get("form_id")
    submission_id = config.get("submission_id") or input_data.get("submission_id")

    if not submission_id:
        raise ValueError("'submission_id' is required")
    if not form_path and not form_id:
        raise ValueError("'form_path' or 'form_id' is required")

    endpoint = (
        f"/{form_path}/submission/{submission_id}"
        if form_path
        else f"/form/{form_id}/submission/{submission_id}"
    )

    log.info("formio.delete_submission", submission_id=submission_id)

    async with await _client(credential_id, db) as client:
        r = await client.delete(endpoint)
        _raise_for_status(r)

    log.info("formio.delete_submission.done", submission_id=submission_id)
    return {"deleted": True, "submission_id": submission_id}
