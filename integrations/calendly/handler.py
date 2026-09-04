"""
Calendly scheduling integration.

Credential fields:
  - api_key: Calendly personal access token

Auth: Authorization: Bearer {api_key}
Base URL: https://api.calendly.com
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.calendly.com"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Calendly credential is missing 'api_key'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
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
        raise ValueError(f"Calendly API error {r.status_code}: {detail}")
    if not r.content:
        return {}
    return r.json()


# ---------------------------------------------------------------------------
# User & Organization
# ---------------------------------------------------------------------------

@register_node("calendly.get_current_user")
async def calendly_get_current_user(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /users/me — get the current authenticated user."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/users/me")
    return _check(r)


@register_node("calendly.get_organization")
async def calendly_get_organization(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /organizations/{uuid} — get an organization by UUID."""
    organization_uri = config.get("organization_uri") or input_data.get("organization_uri")
    uuid = config.get("uuid") or input_data.get("uuid")
    if organization_uri:
        # Extract uuid from URI if full URI provided
        uuid = organization_uri.rstrip("/").split("/")[-1]
    if not uuid:
        raise ValueError("calendly.get_organization requires 'uuid' or 'organization_uri'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/organizations/{uuid}")
    return _check(r)


# ---------------------------------------------------------------------------
# Event Types
# ---------------------------------------------------------------------------

@register_node("calendly.list_event_types")
async def calendly_list_event_types(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /event_types — list event types for a user or organization."""
    params: dict = {}
    user = config.get("user") or input_data.get("user")
    organization = config.get("organization") or input_data.get("organization")
    if user:
        params["user"] = user
    if organization:
        params["organization"] = organization
    if not user and not organization:
        raise ValueError("calendly.list_event_types requires 'user' or 'organization' URI")
    for field in ("active", "count", "page_token", "sort"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            params[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/event_types", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Scheduled Events
# ---------------------------------------------------------------------------

@register_node("calendly.list_scheduled_events")
async def calendly_list_scheduled_events(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /scheduled_events — list scheduled events for a user or organization."""
    params: dict = {}
    user = config.get("user") or input_data.get("user")
    organization = config.get("organization") or input_data.get("organization")
    if user:
        params["user"] = user
    if organization:
        params["organization"] = organization
    if not user and not organization:
        raise ValueError("calendly.list_scheduled_events requires 'user' or 'organization' URI")
    for field in ("count", "invitee_email", "max_start_time", "min_start_time",
                  "page_token", "sort", "status"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            params[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/scheduled_events", params=params)
    return _check(r)


@register_node("calendly.get_event")
async def calendly_get_event(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /scheduled_events/{uuid} — get a scheduled event by UUID."""
    event_uri = config.get("event_uri") or input_data.get("event_uri")
    uuid = config.get("uuid") or input_data.get("uuid")
    if event_uri:
        uuid = event_uri.rstrip("/").split("/")[-1]
    if not uuid:
        raise ValueError("calendly.get_event requires 'uuid' or 'event_uri'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/scheduled_events/{uuid}")
    return _check(r)


@register_node("calendly.list_invitees")
async def calendly_list_invitees(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /scheduled_events/{uuid}/invitees — list invitees for a scheduled event."""
    event_uri = config.get("event_uri") or input_data.get("event_uri")
    uuid = config.get("uuid") or input_data.get("uuid")
    if event_uri:
        uuid = event_uri.rstrip("/").split("/")[-1]
    if not uuid:
        raise ValueError("calendly.list_invitees requires 'uuid' or 'event_uri'")
    params: dict = {}
    for field in ("count", "email", "page_token", "sort", "status"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            params[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/scheduled_events/{uuid}/invitees", params=params)
    return _check(r)


@register_node("calendly.cancel_event")
async def calendly_cancel_event(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /scheduled_events/{uuid}/cancellation — cancel a scheduled event."""
    event_uri = config.get("event_uri") or input_data.get("event_uri")
    uuid = config.get("uuid") or input_data.get("uuid")
    if event_uri:
        uuid = event_uri.rstrip("/").split("/")[-1]
    if not uuid:
        raise ValueError("calendly.cancel_event requires 'uuid' or 'event_uri'")
    body: dict = {}
    reason = config.get("reason") or input_data.get("reason")
    if reason:
        body["reason"] = reason
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/scheduled_events/{uuid}/cancellation", json=body)
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Calendly API error {r.status_code}: {detail}")
    if not r.content:
        return {"ok": True, "uuid": uuid}
    return r.json()


# ---------------------------------------------------------------------------
# Routing Forms
# ---------------------------------------------------------------------------

@register_node("calendly.list_routing_forms")
async def calendly_list_routing_forms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /routing_forms — list routing forms for an organization."""
    organization = config.get("organization") or input_data.get("organization")
    if not organization:
        raise ValueError("calendly.list_routing_forms requires 'organization' URI")
    params: dict = {"organization": organization}
    for field in ("count", "page_token", "sort"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            params[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/routing_forms", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(creds: dict) -> dict:
    """Test Calendly connection by fetching the current user."""
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Missing 'api_key'")
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=30.0,
    ) as client:
        r = await client.get("/users/me")
    if not r.is_success:
        raise ValueError(f"Calendly connection failed: {r.status_code} {r.text}")
    data = r.json()
    resource = data.get("resource", {})
    return {"ok": True, "email": resource.get("email"), "name": resource.get("name")}
