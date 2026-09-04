"""
PostHog product analytics integration.

Credential fields:
  - api_key: PostHog personal API key (for management API)
  - project_id: PostHog project ID

Auth: Authorization: Bearer {api_key}
Base URL: https://app.posthog.com
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

POSTHOG_BASE_URL = "https://app.posthog.com"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("PostHog credential is missing 'api_key'")
    return httpx.AsyncClient(
        base_url=POSTHOG_BASE_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


async def _get_project_id(credential_id: str, db) -> str:
    creds = await get_credential_data(credential_id, db)
    project_id = creds.get("project_id")
    if not project_id:
        raise ValueError("PostHog credential is missing 'project_id'")
    return str(project_id)


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"PostHog API error {r.status_code}: {detail}")
    try:
        return r.json()
    except Exception:
        return {"status": "ok", "text": r.text}


# ---------------------------------------------------------------------------
# Event capture (Capture API)
# ---------------------------------------------------------------------------

@register_node("posthog.capture_event")
async def posthog_capture_event(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /capture/ — capture an event."""
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    distinct_id = config.get("distinct_id") or input_data.get("distinct_id")
    event = config.get("event") or input_data.get("event")
    if not distinct_id or not event:
        raise ValueError("posthog.capture_event requires 'distinct_id' and 'event'")
    body: dict = {
        "api_key": api_key,
        "distinct_id": distinct_id,
        "event": event,
    }
    properties = config.get("properties") or input_data.get("properties")
    if properties:
        body["properties"] = properties
    timestamp = config.get("timestamp") or input_data.get("timestamp")
    if timestamp:
        body["timestamp"] = timestamp
    async with httpx.AsyncClient(base_url=POSTHOG_BASE_URL, timeout=30.0) as client:
        r = await client.post("/capture/", json=body)
    return _check(r)


@register_node("posthog.identify_user")
async def posthog_identify_user(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /capture/ — identify a user with properties ($identify event)."""
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    distinct_id = config.get("distinct_id") or input_data.get("distinct_id")
    if not distinct_id:
        raise ValueError("posthog.identify_user requires 'distinct_id'")
    properties = config.get("properties") or input_data.get("properties") or {}
    body = {
        "api_key": api_key,
        "distinct_id": distinct_id,
        "event": "$identify",
        "properties": {"$set": properties},
    }
    async with httpx.AsyncClient(base_url=POSTHOG_BASE_URL, timeout=30.0) as client:
        r = await client.post("/capture/", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Events (Management API)
# ---------------------------------------------------------------------------

@register_node("posthog.list_events")
async def posthog_list_events(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /api/projects/{project_id}/events/ — list events."""
    project_id = config.get("project_id") or input_data.get("project_id") or await _get_project_id(credential_id, db)
    params = {}
    event = config.get("event") or input_data.get("event")
    if event:
        params["event"] = event
    limit = config.get("limit") or input_data.get("limit")
    if limit:
        params["limit"] = int(limit)
    after = config.get("after") or input_data.get("after")
    if after:
        params["after"] = after
    before = config.get("before") or input_data.get("before")
    if before:
        params["before"] = before
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/api/projects/{project_id}/events/", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Persons
# ---------------------------------------------------------------------------

@register_node("posthog.list_persons")
async def posthog_list_persons(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /api/projects/{project_id}/persons/ — list persons."""
    project_id = config.get("project_id") or input_data.get("project_id") or await _get_project_id(credential_id, db)
    params = {}
    search = config.get("search") or input_data.get("search")
    if search:
        params["search"] = search
    limit = config.get("limit") or input_data.get("limit")
    if limit:
        params["limit"] = int(limit)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/api/projects/{project_id}/persons/", params=params)
    return _check(r)


@register_node("posthog.get_person")
async def posthog_get_person(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /api/projects/{project_id}/persons/{person_id}/ — get a specific person."""
    project_id = config.get("project_id") or input_data.get("project_id") or await _get_project_id(credential_id, db)
    person_id = config.get("person_id") or input_data.get("person_id")
    if not person_id:
        raise ValueError("posthog.get_person requires 'person_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/api/projects/{project_id}/persons/{person_id}/")
    return _check(r)


# ---------------------------------------------------------------------------
# Feature Flags
# ---------------------------------------------------------------------------

@register_node("posthog.list_feature_flags")
async def posthog_list_feature_flags(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /api/projects/{project_id}/feature_flags/ — list feature flags."""
    project_id = config.get("project_id") or input_data.get("project_id") or await _get_project_id(credential_id, db)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/api/projects/{project_id}/feature_flags/")
    return _check(r)


@register_node("posthog.get_feature_flag")
async def posthog_get_feature_flag(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /api/projects/{project_id}/feature_flags/{flag_id}/ — get a feature flag."""
    project_id = config.get("project_id") or input_data.get("project_id") or await _get_project_id(credential_id, db)
    flag_id = config.get("flag_id") or input_data.get("flag_id")
    if not flag_id:
        raise ValueError("posthog.get_feature_flag requires 'flag_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/api/projects/{project_id}/feature_flags/{flag_id}/")
    return _check(r)


# ---------------------------------------------------------------------------
# Cohorts
# ---------------------------------------------------------------------------

@register_node("posthog.list_cohorts")
async def posthog_list_cohorts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /api/projects/{project_id}/cohorts/ — list cohorts."""
    project_id = config.get("project_id") or input_data.get("project_id") or await _get_project_id(credential_id, db)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/api/projects/{project_id}/cohorts/")
    return _check(r)


# ---------------------------------------------------------------------------
# Dashboards
# ---------------------------------------------------------------------------

@register_node("posthog.list_dashboards")
async def posthog_list_dashboards(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /api/projects/{project_id}/dashboards/ — list dashboards."""
    project_id = config.get("project_id") or input_data.get("project_id") or await _get_project_id(credential_id, db)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/api/projects/{project_id}/dashboards/")
    return _check(r)


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------

@register_node("posthog.list_insights")
async def posthog_list_insights(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /api/projects/{project_id}/insights/ — list insights."""
    project_id = config.get("project_id") or input_data.get("project_id") or await _get_project_id(credential_id, db)
    params = {}
    insight_type = config.get("insight") or input_data.get("insight")
    if insight_type:
        params["insight"] = insight_type
    limit = config.get("limit") or input_data.get("limit")
    if limit:
        params["limit"] = int(limit)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/api/projects/{project_id}/insights/", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(credential_id: str, db) -> dict:
    """Test PostHog connection by fetching the current user."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/api/users/@me/")
    _check(r)
    data = r.json()
    return {"ok": True, "email": data.get("email", "unknown")}
