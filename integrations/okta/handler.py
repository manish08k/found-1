"""
Okta integration.

Credential fields:
  - domain: e.g. dev-123.okta.com
  - api_token: Okta API token

Auth: Authorization: SSWS {api_token}
Base URL: https://{domain}/api/v1
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    domain = creds.get("domain", "").rstrip("/")
    api_token = creds.get("api_token")
    if not domain:
        raise ValueError("Okta credential is missing 'domain'")
    if not api_token:
        raise ValueError("Okta credential is missing 'api_token'")
    base_url = f"https://{domain}/api/v1"
    return httpx.AsyncClient(
        base_url=base_url,
        headers={
            "Authorization": f"SSWS {api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Okta API error {r.status_code}: {detail}")
    try:
        return r.json()
    except Exception:
        return {"status": r.status_code, "text": r.text}


async def test_connection(credential_id: str, db) -> dict:
    """Verify credentials by fetching the Okta org."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/org")
    return _check(r)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@register_node("okta.list_users")
async def okta_list_users(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /users — list users."""
    params: dict = {}
    limit = config.get("limit") or input_data.get("limit")
    if limit:
        params["limit"] = int(limit)
    search = config.get("search") or input_data.get("search")
    if search:
        params["search"] = search
    filter_str = config.get("filter") or input_data.get("filter")
    if filter_str:
        params["filter"] = filter_str
    async with await _client(credential_id, db) as client:
        r = await client.get("/users", params=params)
    return {"users": _check(r)}


@register_node("okta.get_user")
async def okta_get_user(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /users/{userId} — get a user by ID or login."""
    user_id = config.get("user_id") or input_data.get("user_id")
    if not user_id:
        raise ValueError("okta.get_user requires 'user_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/users/{user_id}")
    return _check(r)


@register_node("okta.create_user")
async def okta_create_user(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /users — create a new user."""
    profile = config.get("profile") or input_data.get("profile")
    if not profile:
        raise ValueError("okta.create_user requires 'profile' dict with firstName, lastName, email, login")
    body: dict = {"profile": profile}
    credentials = config.get("credentials") or input_data.get("credentials")
    if credentials:
        body["credentials"] = credentials
    activate = config.get("activate")
    if activate is None:
        activate = input_data.get("activate", True)
    params = {"activate": str(activate).lower()}
    async with await _client(credential_id, db) as client:
        r = await client.post("/users", json=body, params=params)
    return _check(r)


@register_node("okta.update_user")
async def okta_update_user(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /users/{userId} — update a user."""
    user_id = config.get("user_id") or input_data.get("user_id")
    if not user_id:
        raise ValueError("okta.update_user requires 'user_id'")
    profile = config.get("profile") or input_data.get("profile")
    if not profile:
        raise ValueError("okta.update_user requires 'profile' dict with fields to update")
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/users/{user_id}", json={"profile": profile})
    return _check(r)


@register_node("okta.deactivate_user")
async def okta_deactivate_user(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /users/{userId}/lifecycle/deactivate — deactivate a user."""
    user_id = config.get("user_id") or input_data.get("user_id")
    if not user_id:
        raise ValueError("okta.deactivate_user requires 'user_id'")
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/users/{user_id}/lifecycle/deactivate")
    return _check(r)


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------

@register_node("okta.list_groups")
async def okta_list_groups(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /groups — list groups."""
    params: dict = {}
    limit = config.get("limit") or input_data.get("limit")
    if limit:
        params["limit"] = int(limit)
    search = config.get("search") or input_data.get("search")
    if search:
        params["search"] = search
    async with await _client(credential_id, db) as client:
        r = await client.get("/groups", params=params)
    return {"groups": _check(r)}


@register_node("okta.get_group")
async def okta_get_group(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /groups/{groupId} — get a group by ID."""
    group_id = config.get("group_id") or input_data.get("group_id")
    if not group_id:
        raise ValueError("okta.get_group requires 'group_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/groups/{group_id}")
    return _check(r)


@register_node("okta.create_group")
async def okta_create_group(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /groups — create a group."""
    name = config.get("name") or input_data.get("name")
    if not name:
        raise ValueError("okta.create_group requires 'name'")
    body: dict = {"profile": {"name": name}}
    description = config.get("description") or input_data.get("description")
    if description:
        body["profile"]["description"] = description
    async with await _client(credential_id, db) as client:
        r = await client.post("/groups", json=body)
    return _check(r)


@register_node("okta.add_user_to_group")
async def okta_add_user_to_group(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /groups/{groupId}/users/{userId} — add a user to a group."""
    group_id = config.get("group_id") or input_data.get("group_id")
    user_id = config.get("user_id") or input_data.get("user_id")
    if not group_id or not user_id:
        raise ValueError("okta.add_user_to_group requires 'group_id' and 'user_id'")
    async with await _client(credential_id, db) as client:
        r = await client.put(f"/groups/{group_id}/users/{user_id}")
    return _check(r)


# ---------------------------------------------------------------------------
# Apps
# ---------------------------------------------------------------------------

@register_node("okta.list_apps")
async def okta_list_apps(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /apps — list applications."""
    params: dict = {}
    limit = config.get("limit") or input_data.get("limit")
    if limit:
        params["limit"] = int(limit)
    filter_str = config.get("filter") or input_data.get("filter")
    if filter_str:
        params["filter"] = filter_str
    async with await _client(credential_id, db) as client:
        r = await client.get("/apps", params=params)
    return {"apps": _check(r)}


# ---------------------------------------------------------------------------
# User Groups (groups for a specific user)
# ---------------------------------------------------------------------------

@register_node("okta.list_user_groups")
async def okta_list_user_groups(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /users/{userId}/groups — list groups for a user."""
    user_id = config.get("user_id") or input_data.get("user_id")
    if not user_id:
        raise ValueError("okta.list_user_groups requires 'user_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/users/{user_id}/groups")
    return {"groups": _check(r)}


# ---------------------------------------------------------------------------
# Factors (MFA)
# ---------------------------------------------------------------------------

@register_node("okta.list_factors")
async def okta_list_factors(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /users/{userId}/factors — list enrolled MFA factors for a user."""
    user_id = config.get("user_id") or input_data.get("user_id")
    if not user_id:
        raise ValueError("okta.list_factors requires 'user_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/users/{user_id}/factors")
    return {"factors": _check(r)}


# ---------------------------------------------------------------------------
# Password Reset
# ---------------------------------------------------------------------------

@register_node("okta.reset_password")
async def okta_reset_password(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /users/{userId}/lifecycle/reset_password — trigger a password reset."""
    user_id = config.get("user_id") or input_data.get("user_id")
    if not user_id:
        raise ValueError("okta.reset_password requires 'user_id'")
    send_email = config.get("send_email")
    if send_email is None:
        send_email = input_data.get("send_email", True)
    params = {"sendEmail": str(send_email).lower()}
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/users/{user_id}/lifecycle/reset_password", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

@register_node("okta.list_roles")
async def okta_list_roles(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /users/{userId}/roles — list roles assigned to a user."""
    user_id = config.get("user_id") or input_data.get("user_id")
    if not user_id:
        raise ValueError("okta.list_roles requires 'user_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/users/{user_id}/roles")
    return {"roles": _check(r)}
