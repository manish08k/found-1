"""
JotForm form builder integration.

Provides form listing, submission retrieval, question fetching, and
submission deletion via the JotForm API.

Credential fields:
  - api_key : JotForm API key (sent as 'apiKey' query parameter)

Base URL: https://api.jotform.com/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://api.jotform.com"


async def _client_pair(credential_id: str, db) -> tuple:
    """Return (AsyncClient, api_key). Enter the context manager at the call site."""
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("jotform credential missing 'api_key'")
    client = httpx.AsyncClient(base_url=_BASE_URL, timeout=30.0)
    return client, api_key


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"JotForm API error {r.status_code}: {detail}")


def _jf_ok(data: dict) -> dict:
    """Raise if JotForm response code indicates an error."""
    code = data.get("responseCode", 200)
    if code >= 300:
        raise ValueError(f"JotForm API returned error code {code}: {data.get('message', data)}")
    return data


@register_node("jotform.list_forms")
async def jotform_list_forms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    List all forms in the JotForm account.

    Config / input_data fields:
      - limit    : max forms to return (default 20, max 1000)
      - offset   : pagination offset (default 0)
      - status   : filter by status: 'ENABLED', 'DISABLED', 'DELETED' (optional)
      - order_by : field to sort by, e.g. 'created_at' (optional)
    """
    limit = min(int(config.get("limit") or input_data.get("limit", 20)), 1000)
    offset = int(config.get("offset") or input_data.get("offset", 0))
    status = config.get("status") or input_data.get("status")
    order_by = config.get("order_by") or input_data.get("order_by")

    client, api_key = await _client_pair(credential_id, db)
    params: dict = {"apiKey": api_key, "limit": limit, "offset": offset}
    if status:
        params["filter"] = f'{{"status":"{status}"}}'
    if order_by:
        params["orderby"] = order_by

    log.info("jotform.list_forms", limit=limit, offset=offset)
    async with client as c:
        r = await c.get("/user/forms", params=params)
        _raise_for_status(r)
        data = _jf_ok(r.json())

    forms = data.get("content", [])
    return {"forms": forms, "count": len(forms), "result_set": data.get("resultSet", {})}


@register_node("jotform.get_submissions")
async def jotform_get_submissions(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Get submissions for a specific form.

    Config / input_data fields:
      - form_id  (required) : JotForm form ID
      - limit               : max submissions to return (default 20, max 1000)
      - offset              : pagination offset (default 0)
      - status              : filter by status, e.g. 'ACTIVE' (optional)
      - order_by            : field to sort by (default 'created_at')
    """
    form_id = config.get("form_id") or input_data.get("form_id")
    if not form_id:
        raise ValueError("jotform.get_submissions requires 'form_id'")

    limit = min(int(config.get("limit") or input_data.get("limit", 20)), 1000)
    offset = int(config.get("offset") or input_data.get("offset", 0))
    status = config.get("status") or input_data.get("status")
    order_by = config.get("order_by") or input_data.get("order_by", "created_at")

    client, api_key = await _client_pair(credential_id, db)
    params: dict = {"apiKey": api_key, "limit": limit, "offset": offset, "orderby": order_by}
    if status:
        params["filter"] = f'{{"status":"{status}"}}'

    log.info("jotform.get_submissions", form_id=form_id, limit=limit)
    async with client as c:
        r = await c.get(f"/form/{form_id}/submissions", params=params)
        _raise_for_status(r)
        data = _jf_ok(r.json())

    submissions = data.get("content", [])
    return {
        "submissions": submissions,
        "count": len(submissions),
        "result_set": data.get("resultSet", {}),
    }


@register_node("jotform.get_form_questions")
async def jotform_get_form_questions(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Retrieve the questions/fields for a specific form.

    Config / input_data fields:
      - form_id (required) : JotForm form ID
    """
    form_id = config.get("form_id") or input_data.get("form_id")
    if not form_id:
        raise ValueError("jotform.get_form_questions requires 'form_id'")

    client, api_key = await _client_pair(credential_id, db)
    log.info("jotform.get_form_questions", form_id=form_id)
    async with client as c:
        r = await c.get(f"/form/{form_id}/questions", params={"apiKey": api_key})
        _raise_for_status(r)
        data = _jf_ok(r.json())

    questions = data.get("content", {})
    questions_list = list(questions.values()) if isinstance(questions, dict) else questions
    return {"questions": questions_list, "count": len(questions_list), "form_id": form_id}


@register_node("jotform.delete_submission")
async def jotform_delete_submission(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Delete a specific form submission.

    Config / input_data fields:
      - submission_id (required) : JotForm submission ID
    """
    submission_id = config.get("submission_id") or input_data.get("submission_id")
    if not submission_id:
        raise ValueError("jotform.delete_submission requires 'submission_id'")

    client, api_key = await _client_pair(credential_id, db)
    log.info("jotform.delete_submission", submission_id=submission_id)
    async with client as c:
        r = await c.delete(f"/submission/{submission_id}", params={"apiKey": api_key})
        _raise_for_status(r)
        data = _jf_ok(r.json())

    return {"deleted": True, "submission_id": submission_id, "response": data.get("content")}
