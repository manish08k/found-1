"""
Segment customer data platform integration.

Credential fields:
  - write_key: Segment source write key (for tracking API)
  - api_token: Segment Public API token (for management API)

Tracking API Auth: HTTP Basic (write_key as username, empty password)
Tracking API Base URL: https://api.segment.io/v1
Public API Auth: Bearer token
Public API Base URL: https://api.segmentapis.com
"""
import base64
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

SEGMENT_TRACKING_URL = "https://api.segment.io/v1"
SEGMENT_PUBLIC_API_URL = "https://api.segmentapis.com"


async def _tracking_client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    write_key = creds.get("write_key")
    if not write_key:
        raise ValueError("Segment credential is missing 'write_key'")
    token = base64.b64encode(f"{write_key}:".encode()).decode()
    return httpx.AsyncClient(
        base_url=SEGMENT_TRACKING_URL,
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


async def _public_api_client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_token = creds.get("api_token")
    if not api_token:
        raise ValueError("Segment credential is missing 'api_token' for Public API access")
    return httpx.AsyncClient(
        base_url=SEGMENT_PUBLIC_API_URL,
        headers={
            "Authorization": f"Bearer {api_token}",
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
        raise ValueError(f"Segment API error {r.status_code}: {detail}")
    try:
        return r.json()
    except Exception:
        return {"status": "ok", "text": r.text}


# ---------------------------------------------------------------------------
# Tracking API
# ---------------------------------------------------------------------------

@register_node("segment.track")
async def segment_track(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /track — track an event for a user."""
    user_id = config.get("user_id") or input_data.get("user_id")
    event = config.get("event") or input_data.get("event")
    if not event:
        raise ValueError("segment.track requires 'event'")
    if not user_id and not (config.get("anonymous_id") or input_data.get("anonymous_id")):
        raise ValueError("segment.track requires 'user_id' or 'anonymous_id'")
    body: dict = {"event": event}
    if user_id:
        body["userId"] = user_id
    anonymous_id = config.get("anonymous_id") or input_data.get("anonymous_id")
    if anonymous_id:
        body["anonymousId"] = anonymous_id
    properties = config.get("properties") or input_data.get("properties")
    if properties:
        body["properties"] = properties
    context = config.get("context") or input_data.get("context")
    if context:
        body["context"] = context
    timestamp = config.get("timestamp") or input_data.get("timestamp")
    if timestamp:
        body["timestamp"] = timestamp
    async with await _tracking_client(credential_id, db) as client:
        r = await client.post("/track", json=body)
    return _check(r)


@register_node("segment.identify")
async def segment_identify(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /identify — identify a user with traits."""
    user_id = config.get("user_id") or input_data.get("user_id")
    if not user_id:
        raise ValueError("segment.identify requires 'user_id'")
    body: dict = {"userId": user_id}
    traits = config.get("traits") or input_data.get("traits")
    if traits:
        body["traits"] = traits
    context = config.get("context") or input_data.get("context")
    if context:
        body["context"] = context
    async with await _tracking_client(credential_id, db) as client:
        r = await client.post("/identify", json=body)
    return _check(r)


@register_node("segment.page")
async def segment_page(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /page — record a page view."""
    user_id = config.get("user_id") or input_data.get("user_id")
    anonymous_id = config.get("anonymous_id") or input_data.get("anonymous_id")
    if not user_id and not anonymous_id:
        raise ValueError("segment.page requires 'user_id' or 'anonymous_id'")
    body: dict = {}
    if user_id:
        body["userId"] = user_id
    if anonymous_id:
        body["anonymousId"] = anonymous_id
    name = config.get("name") or input_data.get("name")
    if name:
        body["name"] = name
    properties = config.get("properties") or input_data.get("properties")
    if properties:
        body["properties"] = properties
    async with await _tracking_client(credential_id, db) as client:
        r = await client.post("/page", json=body)
    return _check(r)


@register_node("segment.group")
async def segment_group(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /group — associate a user with a group."""
    user_id = config.get("user_id") or input_data.get("user_id")
    group_id = config.get("group_id") or input_data.get("group_id")
    if not user_id or not group_id:
        raise ValueError("segment.group requires 'user_id' and 'group_id'")
    body: dict = {"userId": user_id, "groupId": group_id}
    traits = config.get("traits") or input_data.get("traits")
    if traits:
        body["traits"] = traits
    async with await _tracking_client(credential_id, db) as client:
        r = await client.post("/group", json=body)
    return _check(r)


@register_node("segment.alias")
async def segment_alias(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /alias — merge two user identities."""
    user_id = config.get("user_id") or input_data.get("user_id")
    previous_id = config.get("previous_id") or input_data.get("previous_id")
    if not user_id or not previous_id:
        raise ValueError("segment.alias requires 'user_id' and 'previous_id'")
    body = {"userId": user_id, "previousId": previous_id}
    async with await _tracking_client(credential_id, db) as client:
        r = await client.post("/alias", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Public API (Management)
# ---------------------------------------------------------------------------

@register_node("segment.list_sources")
async def segment_list_sources(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /sources — list all sources in the workspace."""
    params = {}
    pagination = config.get("pagination") or input_data.get("pagination")
    if pagination:
        params.update(pagination)
    async with await _public_api_client(credential_id, db) as client:
        r = await client.get("/sources", params=params)
    return _check(r)


@register_node("segment.list_destinations")
async def segment_list_destinations(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /destinations — list all destinations in the workspace."""
    params = {}
    source_id = config.get("source_id") or input_data.get("source_id")
    if source_id:
        params["sourceId"] = source_id
    async with await _public_api_client(credential_id, db) as client:
        r = await client.get("/destinations", params=params)
    return _check(r)


@register_node("segment.list_workspaces")
async def segment_list_workspaces(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /workspaces — get workspace information."""
    async with await _public_api_client(credential_id, db) as client:
        r = await client.get("/workspaces")
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(credential_id: str, db) -> dict:
    """Test Segment connection by calling the identify endpoint with a test event."""
    creds = await get_credential_data(credential_id, db)
    write_key = creds.get("write_key")
    if not write_key:
        raise ValueError("Segment credential is missing 'write_key'")
    token = base64.b64encode(f"{write_key}:".encode()).decode()
    test_body = {
        "userId": "test_connection_check",
        "traits": {"source": "connection_test"},
    }
    async with httpx.AsyncClient(
        base_url=SEGMENT_TRACKING_URL,
        headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"},
        timeout=30.0,
    ) as client:
        r = await client.post("/identify", json=test_body)
    _check(r)
    return {"ok": True, "message": "Segment connection successful"}
