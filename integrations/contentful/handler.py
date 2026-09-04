"""
Contentful CMS integration.

Credential fields:
  - space_id: Contentful space ID
  - access_token: Content Delivery API token (read-only)
  - management_token: Content Management API token (read/write)

Delivery API: https://cdn.contentful.com/spaces/{space_id}
Management API: https://api.contentful.com/spaces/{space_id}
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _delivery_client(credential_id: str, db) -> httpx.AsyncClient:
    """Client for Content Delivery API (read-only)."""
    creds = await get_credential_data(credential_id, db)
    space_id = creds.get("space_id")
    access_token = creds.get("access_token")
    if not space_id:
        raise ValueError("Contentful credential is missing 'space_id'")
    if not access_token:
        raise ValueError("Contentful credential is missing 'access_token'")
    return httpx.AsyncClient(
        base_url=f"https://cdn.contentful.com/spaces/{space_id}",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


async def _management_client(credential_id: str, db) -> httpx.AsyncClient:
    """Client for Content Management API (read/write)."""
    creds = await get_credential_data(credential_id, db)
    space_id = creds.get("space_id")
    management_token = creds.get("management_token")
    if not space_id:
        raise ValueError("Contentful credential is missing 'space_id'")
    if not management_token:
        raise ValueError("Contentful credential is missing 'management_token'")
    return httpx.AsyncClient(
        base_url=f"https://api.contentful.com/spaces/{space_id}",
        headers={
            "Authorization": f"Bearer {management_token}",
            "Content-Type": "application/vnd.contentful.management.v1+json",
        },
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Contentful API error {r.status_code}: {detail}")
    return r.json()


async def test_connection(credential_id: str, db) -> dict:
    """Verify credentials by fetching space info."""
    async with await _management_client(credential_id, db) as client:
        r = await client.get("")
    data = _check(r)
    return {"ok": True, "space_name": data.get("name"), "space_id": data.get("sys", {}).get("id")}


# ---------------------------------------------------------------------------
# Entries
# ---------------------------------------------------------------------------

@register_node("contentful.list_entries")
async def contentful_list_entries(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /entries — list entries via Delivery API."""
    params = {}
    for key in ("content_type", "limit", "skip", "order", "select", "include", "locale"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    env = config.get("environment", input_data.get("environment", "master"))
    async with await _delivery_client(credential_id, db) as client:
        r = await client.get(f"/environments/{env}/entries", params=params)
    return _check(r)


@register_node("contentful.get_entry")
async def contentful_get_entry(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /entries/{entry_id} — get a single entry via Delivery API."""
    entry_id = config.get("entry_id") or input_data.get("entry_id")
    if not entry_id:
        raise ValueError("contentful.get_entry requires 'entry_id'")
    env = config.get("environment", input_data.get("environment", "master"))
    async with await _delivery_client(credential_id, db) as client:
        r = await client.get(f"/environments/{env}/entries/{entry_id}")
    return _check(r)


@register_node("contentful.create_entry")
async def contentful_create_entry(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /entries — create an entry via Management API."""
    content_type_id = config.get("content_type_id") or input_data.get("content_type_id")
    fields = config.get("fields") or input_data.get("fields")
    if not content_type_id:
        raise ValueError("contentful.create_entry requires 'content_type_id'")
    if not fields:
        raise ValueError("contentful.create_entry requires 'fields'")
    env = config.get("environment", input_data.get("environment", "master"))
    async with await _management_client(credential_id, db) as client:
        r = await client.post(
            f"/environments/{env}/entries",
            json={"fields": fields},
            headers={"X-Contentful-Content-Type": content_type_id},
        )
    return _check(r)


@register_node("contentful.update_entry")
async def contentful_update_entry(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /entries/{entry_id} — update an entry via Management API."""
    entry_id = config.get("entry_id") or input_data.get("entry_id")
    fields = config.get("fields") or input_data.get("fields")
    version = config.get("version") or input_data.get("version")
    if not entry_id:
        raise ValueError("contentful.update_entry requires 'entry_id'")
    if not fields:
        raise ValueError("contentful.update_entry requires 'fields'")
    if not version:
        raise ValueError("contentful.update_entry requires 'version' (X-Contentful-Version)")
    env = config.get("environment", input_data.get("environment", "master"))
    async with await _management_client(credential_id, db) as client:
        r = await client.put(
            f"/environments/{env}/entries/{entry_id}",
            json={"fields": fields},
            headers={"X-Contentful-Version": str(version)},
        )
    return _check(r)


@register_node("contentful.publish_entry")
async def contentful_publish_entry(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /entries/{entry_id}/published — publish an entry."""
    entry_id = config.get("entry_id") or input_data.get("entry_id")
    version = config.get("version") or input_data.get("version")
    if not entry_id:
        raise ValueError("contentful.publish_entry requires 'entry_id'")
    if not version:
        raise ValueError("contentful.publish_entry requires 'version'")
    env = config.get("environment", input_data.get("environment", "master"))
    async with await _management_client(credential_id, db) as client:
        r = await client.put(
            f"/environments/{env}/entries/{entry_id}/published",
            headers={"X-Contentful-Version": str(version)},
        )
    return _check(r)


@register_node("contentful.unpublish_entry")
async def contentful_unpublish_entry(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /entries/{entry_id}/published — unpublish an entry."""
    entry_id = config.get("entry_id") or input_data.get("entry_id")
    if not entry_id:
        raise ValueError("contentful.unpublish_entry requires 'entry_id'")
    env = config.get("environment", input_data.get("environment", "master"))
    async with await _management_client(credential_id, db) as client:
        r = await client.delete(f"/environments/{env}/entries/{entry_id}/published")
    if r.status_code == 200:
        return r.json()
    if r.status_code == 204:
        return {"unpublished": True, "entry_id": entry_id}
    return _check(r)


@register_node("contentful.delete_entry")
async def contentful_delete_entry(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /entries/{entry_id} — delete an entry."""
    entry_id = config.get("entry_id") or input_data.get("entry_id")
    if not entry_id:
        raise ValueError("contentful.delete_entry requires 'entry_id'")
    env = config.get("environment", input_data.get("environment", "master"))
    async with await _management_client(credential_id, db) as client:
        r = await client.delete(f"/environments/{env}/entries/{entry_id}")
    if r.status_code == 204:
        return {"deleted": True, "entry_id": entry_id}
    return _check(r)


# ---------------------------------------------------------------------------
# Content Types
# ---------------------------------------------------------------------------

@register_node("contentful.list_content_types")
async def contentful_list_content_types(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /content_types — list content types via Delivery API."""
    params = {}
    limit = config.get("limit") or input_data.get("limit")
    if limit:
        params["limit"] = limit
    env = config.get("environment", input_data.get("environment", "master"))
    async with await _delivery_client(credential_id, db) as client:
        r = await client.get(f"/environments/{env}/content_types", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------

@register_node("contentful.list_assets")
async def contentful_list_assets(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /assets — list assets via Delivery API."""
    params = {}
    for key in ("limit", "skip", "order", "locale"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    env = config.get("environment", input_data.get("environment", "master"))
    async with await _delivery_client(credential_id, db) as client:
        r = await client.get(f"/environments/{env}/assets", params=params)
    return _check(r)


@register_node("contentful.get_asset")
async def contentful_get_asset(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /assets/{asset_id} — get a single asset."""
    asset_id = config.get("asset_id") or input_data.get("asset_id")
    if not asset_id:
        raise ValueError("contentful.get_asset requires 'asset_id'")
    env = config.get("environment", input_data.get("environment", "master"))
    async with await _delivery_client(credential_id, db) as client:
        r = await client.get(f"/environments/{env}/assets/{asset_id}")
    return _check(r)


# ---------------------------------------------------------------------------
# Locales
# ---------------------------------------------------------------------------

@register_node("contentful.list_locales")
async def contentful_list_locales(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /locales — list locales for the space."""
    env = config.get("environment", input_data.get("environment", "master"))
    async with await _delivery_client(credential_id, db) as client:
        r = await client.get(f"/environments/{env}/locales")
    return _check(r)
