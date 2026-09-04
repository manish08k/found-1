"""
SurveyMonkey integration.

Credential fields:
  - access_token: OAuth2 access token

Auth: Authorization: Bearer {access_token}
Base URL: https://api.surveymonkey.com/v3
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.surveymonkey.com/v3"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    access_token = creds.get("access_token")
    if not access_token:
        raise ValueError("SurveyMonkey credential is missing 'access_token'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
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
        raise ValueError(f"SurveyMonkey API error {r.status_code}: {detail}")
    return r.json()


async def test_connection(credential_id: str, db) -> dict:
    """Verify credentials by fetching current user info."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/users/me")
    return _check(r)


# ---------------------------------------------------------------------------
# Surveys
# ---------------------------------------------------------------------------

@register_node("surveymonkey.list_surveys")
async def surveymonkey_list_surveys(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /surveys — list all surveys."""
    params = {}
    page = config.get("page") or input_data.get("page")
    if page:
        params["page"] = int(page)
    per_page = config.get("per_page") or input_data.get("per_page")
    if per_page:
        params["per_page"] = min(int(per_page), 1000)
    sort_by = config.get("sort_by") or input_data.get("sort_by")
    if sort_by:
        params["sort_by"] = sort_by
    async with await _client(credential_id, db) as client:
        r = await client.get("/surveys", params=params)
    return _check(r)


@register_node("surveymonkey.get_survey")
async def surveymonkey_get_survey(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /surveys/{survey_id} — get survey details."""
    survey_id = config.get("survey_id") or input_data.get("survey_id")
    if not survey_id:
        raise ValueError("surveymonkey.get_survey requires 'survey_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/surveys/{survey_id}/details")
    return _check(r)


@register_node("surveymonkey.create_survey")
async def surveymonkey_create_survey(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /surveys — create a new survey."""
    title = config.get("title") or input_data.get("title")
    if not title:
        raise ValueError("surveymonkey.create_survey requires 'title'")
    body: dict = {"title": title}
    for field in ("nickname", "language", "category"):
        v = config.get(field) or input_data.get(field)
        if v:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/surveys", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Pages & Questions
# ---------------------------------------------------------------------------

@register_node("surveymonkey.list_pages")
async def surveymonkey_list_pages(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /surveys/{survey_id}/pages — list pages in a survey."""
    survey_id = config.get("survey_id") or input_data.get("survey_id")
    if not survey_id:
        raise ValueError("surveymonkey.list_pages requires 'survey_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/surveys/{survey_id}/pages")
    return _check(r)


@register_node("surveymonkey.list_questions")
async def surveymonkey_list_questions(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /surveys/{survey_id}/pages/{page_id}/questions — list questions on a page."""
    survey_id = config.get("survey_id") or input_data.get("survey_id")
    page_id = config.get("page_id") or input_data.get("page_id")
    if not survey_id or not page_id:
        raise ValueError("surveymonkey.list_questions requires 'survey_id' and 'page_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/surveys/{survey_id}/pages/{page_id}/questions")
    return _check(r)


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

@register_node("surveymonkey.list_responses")
async def surveymonkey_list_responses(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /surveys/{survey_id}/responses/bulk — list survey responses."""
    survey_id = config.get("survey_id") or input_data.get("survey_id")
    if not survey_id:
        raise ValueError("surveymonkey.list_responses requires 'survey_id'")
    params = {}
    per_page = config.get("per_page") or input_data.get("per_page")
    if per_page:
        params["per_page"] = int(per_page)
    page = config.get("page") or input_data.get("page")
    if page:
        params["page"] = int(page)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/surveys/{survey_id}/responses/bulk", params=params)
    return _check(r)


@register_node("surveymonkey.get_response")
async def surveymonkey_get_response(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /surveys/{survey_id}/responses/{response_id} — get a specific response."""
    survey_id = config.get("survey_id") or input_data.get("survey_id")
    response_id = config.get("response_id") or input_data.get("response_id")
    if not survey_id or not response_id:
        raise ValueError("surveymonkey.get_response requires 'survey_id' and 'response_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/surveys/{survey_id}/responses/{response_id}")
    return _check(r)


# ---------------------------------------------------------------------------
# Collectors
# ---------------------------------------------------------------------------

@register_node("surveymonkey.list_collectors")
async def surveymonkey_list_collectors(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /surveys/{survey_id}/collectors — list collectors for a survey."""
    survey_id = config.get("survey_id") or input_data.get("survey_id")
    if not survey_id:
        raise ValueError("surveymonkey.list_collectors requires 'survey_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/surveys/{survey_id}/collectors")
    return _check(r)


@register_node("surveymonkey.create_collector")
async def surveymonkey_create_collector(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /surveys/{survey_id}/collectors — create a collector."""
    survey_id = config.get("survey_id") or input_data.get("survey_id")
    if not survey_id:
        raise ValueError("surveymonkey.create_collector requires 'survey_id'")
    body: dict = {}
    collector_type = config.get("type") or input_data.get("type", "weblink")
    body["type"] = collector_type
    name = config.get("name") or input_data.get("name")
    if name:
        body["name"] = name
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/surveys/{survey_id}/collectors", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

@register_node("surveymonkey.list_contacts")
async def surveymonkey_list_contacts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /contacts — list contacts."""
    params = {}
    page = config.get("page") or input_data.get("page")
    if page:
        params["page"] = int(page)
    per_page = config.get("per_page") or input_data.get("per_page")
    if per_page:
        params["per_page"] = int(per_page)
    async with await _client(credential_id, db) as client:
        r = await client.get("/contacts", params=params)
    return _check(r)


@register_node("surveymonkey.list_contact_lists")
async def surveymonkey_list_contact_lists(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /contact_lists — list contact lists."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/contact_lists")
    return _check(r)
