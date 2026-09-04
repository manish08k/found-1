"""
Strapi CMS integration.

Credential fields:
  - base_url: https://myapp.strapi.io
  - api_token: Strapi API token

Auth: Authorization: Bearer {api_token}
Base URL: {base_url}/api
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    base_url = creds.get("base_url", "").rstrip("/")
    api_token = creds.get("api_token")
    if not base_url:
        raise ValueError("Strapi credential is missing 'base_url'")
    if not api_token:
        raise ValueError("Strapi credential is missing 'api_token'")
    return httpx.AsyncClient(
        base_url=f"{base_url}/api",
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
        raise ValueError(f"Strapi API error {r.status_code}: {detail}")
    return r.json()


async def test_connection(credential_id: str, db) -> dict:
    """Verify credentials by fetching current user info."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/users/me")
    data = _check(r)
    return {"ok": True, "username": data.get("username"), "email": data.get("email")}


# ---------------------------------------------------------------------------
# Entries (generic collection operations)
# ---------------------------------------------------------------------------

@register_node("strapi.find_entries")
async def strapi_find_entries(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /{collection_type} — list entries in a collection."""
    collection_type = config.get("collection_type") or input_data.get("collection_type")
    if not collection_type:
        raise ValueError("strapi.find_entries requires 'collection_type'")
    params = {}
    for key in ("pagination[page]", "pagination[pageSize]", "sort", "filters", "populate", "fields", "locale"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/{collection_type}", params=params)
    return _check(r)


@register_node("strapi.find_one")
async def strapi_find_one(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /{collection_type}/{id} — get a single entry."""
    collection_type = config.get("collection_type") or input_data.get("collection_type")
    entry_id = config.get("entry_id") or input_data.get("entry_id")
    if not collection_type:
        raise ValueError("strapi.find_one requires 'collection_type'")
    if not entry_id:
        raise ValueError("strapi.find_one requires 'entry_id'")
    params = {}
    populate = config.get("populate") or input_data.get("populate")
    if populate:
        params["populate"] = populate
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/{collection_type}/{entry_id}", params=params)
    return _check(r)


@register_node("strapi.create_entry")
async def strapi_create_entry(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /{collection_type} — create a new entry."""
    collection_type = config.get("collection_type") or input_data.get("collection_type")
    if not collection_type:
        raise ValueError("strapi.create_entry requires 'collection_type'")
    data = config.get("data") or input_data.get("data")
    if not data:
        raise ValueError("strapi.create_entry requires 'data'")
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/{collection_type}", json={"data": data})
    return _check(r)


@register_node("strapi.update_entry")
async def strapi_update_entry(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /{collection_type}/{id} — update an entry."""
    collection_type = config.get("collection_type") or input_data.get("collection_type")
    entry_id = config.get("entry_id") or input_data.get("entry_id")
    if not collection_type:
        raise ValueError("strapi.update_entry requires 'collection_type'")
    if not entry_id:
        raise ValueError("strapi.update_entry requires 'entry_id'")
    data = config.get("data") or input_data.get("data")
    if not data:
        raise ValueError("strapi.update_entry requires 'data'")
    async with await _client(credential_id, db) as client:
        r = await client.put(f"/{collection_type}/{entry_id}", json={"data": data})
    return _check(r)


@register_node("strapi.delete_entry")
async def strapi_delete_entry(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /{collection_type}/{id} — delete an entry."""
    collection_type = config.get("collection_type") or input_data.get("collection_type")
    entry_id = config.get("entry_id") or input_data.get("entry_id")
    if not collection_type:
        raise ValueError("strapi.delete_entry requires 'collection_type'")
    if not entry_id:
        raise ValueError("strapi.delete_entry requires 'entry_id'")
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/{collection_type}/{entry_id}")
    return _check(r)


# ---------------------------------------------------------------------------
# Content Types
# ---------------------------------------------------------------------------

@register_node("strapi.get_collection_types")
async def strapi_get_collection_types(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /content-type-builder/content-types — list available content types."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/content-type-builder/content-types")
    return _check(r)


# ---------------------------------------------------------------------------
# Files / Media
# ---------------------------------------------------------------------------

@register_node("strapi.upload_file")
async def strapi_upload_file(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /upload — upload a file."""
    file_url = config.get("file_url") or input_data.get("file_url")
    file_content = config.get("file_content") or input_data.get("file_content")
    filename = config.get("filename") or input_data.get("filename", "upload.bin")
    mime_type = config.get("mime_type") or input_data.get("mime_type", "application/octet-stream")
    if not file_url and not file_content:
        raise ValueError("strapi.upload_file requires 'file_url' or 'file_content'")
    if file_url:
        async with httpx.AsyncClient() as fetch_client:
            fr = await fetch_client.get(file_url)
        file_bytes = fr.content
    else:
        import base64
        file_bytes = base64.b64decode(file_content)
    creds = await get_credential_data(credential_id, db)
    base_url = creds.get("base_url", "").rstrip("/")
    api_token = creds.get("api_token")
    async with httpx.AsyncClient(
        base_url=f"{base_url}/api",
        headers={"Authorization": f"Bearer {api_token}"},
        timeout=60.0,
    ) as client:
        files = {"files": (filename, file_bytes, mime_type)}
        r = await client.post("/upload", files=files)
    return _check(r)


@register_node("strapi.list_files")
async def strapi_list_files(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /upload/files — list uploaded files."""
    params = {}
    for key in ("page", "pageSize", "sort", "filters"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/upload/files", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@register_node("strapi.get_user")
async def strapi_get_user(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /users/{id} — get a user by ID (or /users/me)."""
    user_id = config.get("user_id") or input_data.get("user_id", "me")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/users/{user_id}")
    return _check(r)


@register_node("strapi.list_users")
async def strapi_list_users(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /users — list all users."""
    params = {}
    for key in ("page", "pageSize", "sort", "filters", "populate"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/users", params=params)
    return _check(r)
