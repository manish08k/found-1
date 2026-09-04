"""
Netlify hosting and deployment integration.

Credential fields:
  - api_key: Netlify personal access token

Auth: Authorization: Bearer {api_key}
Base URL: https://api.netlify.com/api/v1
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

NETLIFY_BASE_URL = "https://api.netlify.com/api/v1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Netlify credential is missing 'api_key'")
    return httpx.AsyncClient(
        base_url=NETLIFY_BASE_URL,
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
        raise ValueError(f"Netlify API error {r.status_code}: {detail}")
    try:
        return r.json()
    except Exception:
        return {"status": "ok", "text": r.text}


# ---------------------------------------------------------------------------
# Sites
# ---------------------------------------------------------------------------

@register_node("netlify.list_sites")
async def netlify_list_sites(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /sites — list all sites for the authenticated user."""
    params = {}
    filter_val = config.get("filter") or input_data.get("filter")
    if filter_val:
        params["filter"] = filter_val
    async with await _client(credential_id, db) as client:
        r = await client.get("/sites", params=params)
    return _check(r)


@register_node("netlify.get_site")
async def netlify_get_site(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /sites/{site_id} — get a specific site by ID."""
    site_id = config.get("site_id") or input_data.get("site_id")
    if not site_id:
        raise ValueError("netlify.get_site requires 'site_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/sites/{site_id}")
    return _check(r)


@register_node("netlify.create_site")
async def netlify_create_site(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /sites — create a new site."""
    body: dict = {}
    for field in ("name", "custom_domain", "password", "force_ssl"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/sites", json=body)
    return _check(r)


@register_node("netlify.update_site")
async def netlify_update_site(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PATCH /sites/{site_id} — update a site."""
    site_id = config.get("site_id") or input_data.get("site_id")
    if not site_id:
        raise ValueError("netlify.update_site requires 'site_id'")
    body: dict = {}
    for field in ("name", "custom_domain", "password", "force_ssl", "build_settings"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.patch(f"/sites/{site_id}", json=body)
    return _check(r)


@register_node("netlify.delete_site")
async def netlify_delete_site(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /sites/{site_id} — delete a site."""
    site_id = config.get("site_id") or input_data.get("site_id")
    if not site_id:
        raise ValueError("netlify.delete_site requires 'site_id'")
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/sites/{site_id}")
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Netlify API error {r.status_code}: {detail}")
    return {"deleted": True, "site_id": site_id}


# ---------------------------------------------------------------------------
# Deploys
# ---------------------------------------------------------------------------

@register_node("netlify.list_deploys")
async def netlify_list_deploys(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /sites/{site_id}/deploys — list deploys for a site."""
    site_id = config.get("site_id") or input_data.get("site_id")
    if not site_id:
        raise ValueError("netlify.list_deploys requires 'site_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/sites/{site_id}/deploys")
    return _check(r)


@register_node("netlify.get_deploy")
async def netlify_get_deploy(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /deploys/{deploy_id} — get a specific deploy by ID."""
    deploy_id = config.get("deploy_id") or input_data.get("deploy_id")
    if not deploy_id:
        raise ValueError("netlify.get_deploy requires 'deploy_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/deploys/{deploy_id}")
    return _check(r)


@register_node("netlify.trigger_deploy")
async def netlify_trigger_deploy(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /sites/{site_id}/builds — trigger a new deploy/build for a site."""
    site_id = config.get("site_id") or input_data.get("site_id")
    if not site_id:
        raise ValueError("netlify.trigger_deploy requires 'site_id'")
    body: dict = {}
    clear_cache = config.get("clear_cache")
    if clear_cache is None:
        clear_cache = input_data.get("clear_cache")
    if clear_cache is not None:
        body["clear_cache"] = bool(clear_cache)
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/sites/{site_id}/builds", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Forms & Submissions
# ---------------------------------------------------------------------------

@register_node("netlify.list_forms")
async def netlify_list_forms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /sites/{site_id}/forms — list forms for a site."""
    site_id = config.get("site_id") or input_data.get("site_id")
    if not site_id:
        raise ValueError("netlify.list_forms requires 'site_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/sites/{site_id}/forms")
    return _check(r)


@register_node("netlify.list_submissions")
async def netlify_list_submissions(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /forms/{form_id}/submissions — list submissions for a form."""
    form_id = config.get("form_id") or input_data.get("form_id")
    if not form_id:
        raise ValueError("netlify.list_submissions requires 'form_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/forms/{form_id}/submissions")
    return _check(r)


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------

@register_node("netlify.list_hooks")
async def netlify_list_hooks(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /hooks — list notification hooks."""
    params = {}
    site_id = config.get("site_id") or input_data.get("site_id")
    if site_id:
        params["site_id"] = site_id
    async with await _client(credential_id, db) as client:
        r = await client.get("/hooks", params=params)
    return _check(r)


@register_node("netlify.create_hook")
async def netlify_create_hook(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /hooks — create a notification hook."""
    site_id = config.get("site_id") or input_data.get("site_id")
    hook_type = config.get("type") or input_data.get("type")
    event = config.get("event") or input_data.get("event")
    data = config.get("data") or input_data.get("data")
    if not site_id or not hook_type or not event:
        raise ValueError("netlify.create_hook requires 'site_id', 'type', and 'event'")
    body: dict = {"site_id": site_id, "type": hook_type, "event": event}
    if data:
        body["data"] = data
    async with await _client(credential_id, db) as client:
        r = await client.post("/hooks", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(credential_id: str, db) -> dict:
    """Test Netlify connection by fetching the current user info."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/user")
    _check(r)
    data = r.json()
    return {"ok": True, "email": data.get("email", "unknown")}
