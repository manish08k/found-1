"""
Formstack integration.

Provides form listing, submission retrieval, form details, and
submission deletion via the Formstack API v2.

Credential fields:
  - access_token : Formstack OAuth2 access token or API key

Auth: Bearer token via Authorization header.
Base URL: https://www.formstack.com/api/v2/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

FORMSTACK_BASE = "https://www.formstack.com/api/v2"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    access_token = creds.get("access_token")
    if not access_token:
        raise ValueError("Formstack credential missing 'access_token'")
    return httpx.AsyncClient(
        base_url=FORMSTACK_BASE,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 400:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise RuntimeError(f"Formstack API error {r.status_code}: {detail}")


@register_node("formstack.list_forms")
async def list_forms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all Formstack forms available to the authenticated user."""
    page = int(config.get("page", 1))
    per_page = int(config.get("per_page", 25))
    folder_id = config.get("folder_id") or input_data.get("folder_id")
    search = config.get("search") or input_data.get("search")

    params: dict = {
        "page": page,
        "per_page": per_page,
        "fields": "id,name,url,created,updated,submissions,views",
    }
    if folder_id:
        params["folder"] = folder_id
    if search:
        params["search"] = search

    log.info("formstack.list_forms", page=page, per_page=per_page)

    async with await _client(credential_id, db) as client:
        r = await client.get("/form.json", params=params)
        _raise_for_status(r)
        data = r.json()

    forms = data.get("forms", [])
    total = data.get("total", len(forms))
    log.info("formstack.list_forms.done", count=len(forms), total=total)
    return {"forms": forms, "count": len(forms), "total": total, "page": page}


@register_node("formstack.get_submissions")
async def get_submissions(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve submissions for a given Formstack form."""
    form_id = config.get("form_id") or input_data.get("form_id")
    if not form_id:
        raise ValueError("'form_id' is required in config or input_data")

    page = int(config.get("page", 1))
    per_page = int(config.get("per_page", 25))
    sort = config.get("sort", "DESC")  # ASC or DESC
    min_time = config.get("min_time") or input_data.get("min_time")
    max_time = config.get("max_time") or input_data.get("max_time")
    search_field = config.get("search_field")
    search_value = config.get("search_value")
    expand_data = config.get("expand_data", True)

    params: dict = {
        "page": page,
        "per_page": per_page,
        "sort": sort,
        "expand_data": 1 if expand_data else 0,
    }
    if min_time:
        params["min_time"] = min_time
    if max_time:
        params["max_time"] = max_time
    if search_field:
        params["search_field"] = search_field
    if search_value:
        params["search_value"] = search_value

    log.info("formstack.get_submissions", form_id=form_id, page=page, per_page=per_page)

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/form/{form_id}/submission.json", params=params)
        _raise_for_status(r)
        data = r.json()

    submissions = data.get("submissions", [])
    total = data.get("total", len(submissions))
    log.info("formstack.get_submissions.done", form_id=form_id, count=len(submissions))
    return {
        "submissions": submissions,
        "count": len(submissions),
        "total": total,
        "page": page,
        "form_id": form_id,
    }


@register_node("formstack.get_form")
async def get_form(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve detailed information about a specific Formstack form."""
    form_id = config.get("form_id") or input_data.get("form_id")
    if not form_id:
        raise ValueError("'form_id' is required in config or input_data")

    include_fields = config.get("include_fields", True)

    params: dict = {}
    if include_fields:
        params["fields"] = 1

    log.info("formstack.get_form", form_id=form_id)

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/form/{form_id}.json", params=params)
        _raise_for_status(r)
        form = r.json()

    log.info("formstack.get_form.done", form_id=form_id, name=form.get("name"))
    return {"form": form}


@register_node("formstack.delete_submission")
async def delete_submission(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Delete a specific submission from a Formstack form."""
    submission_id = config.get("submission_id") or input_data.get("submission_id")
    if not submission_id:
        raise ValueError("'submission_id' is required in config or input_data")

    log.info("formstack.delete_submission", submission_id=submission_id)

    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/submission/{submission_id}.json")
        _raise_for_status(r)

    log.info("formstack.delete_submission.done", submission_id=submission_id)
    return {"deleted": True, "submission_id": submission_id}
