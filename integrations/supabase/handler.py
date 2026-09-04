"""
Supabase backend-as-a-service integration.

Credential fields:
  - url: Project URL (e.g. https://xxx.supabase.co)
  - anon_key: Anon/public key (or service_role_key for elevated access)
  - service_role_key: Service role key (optional, overrides anon_key if provided)

Auth: apikey header + Authorization: Bearer header
Base URL: {url}/rest/v1  (PostgREST)
Storage: {url}/storage/v1
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _get_creds(credential_id: str, db) -> dict:
    creds = await get_credential_data(credential_id, db)
    url = creds.get("url", "").rstrip("/")
    if not url:
        raise ValueError("Supabase credential is missing 'url'")
    key = creds.get("service_role_key") or creds.get("anon_key")
    if not key:
        raise ValueError("Supabase credential is missing 'anon_key' or 'service_role_key'")
    return {"url": url, "key": key}


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    info = await _get_creds(credential_id, db)
    return httpx.AsyncClient(
        base_url=f"{info['url']}/rest/v1",
        headers={
            "apikey": info["key"],
            "Authorization": f"Bearer {info['key']}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        timeout=30.0,
    )


async def _storage_client(credential_id: str, db) -> httpx.AsyncClient:
    info = await _get_creds(credential_id, db)
    return httpx.AsyncClient(
        base_url=f"{info['url']}/storage/v1",
        headers={
            "apikey": info["key"],
            "Authorization": f"Bearer {info['key']}",
        },
        timeout=60.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Supabase API error {r.status_code}: {detail}")
    try:
        return r.json()
    except Exception:
        return {"status": "ok", "text": r.text}


# ---------------------------------------------------------------------------
# PostgREST Database Operations
# ---------------------------------------------------------------------------

@register_node("supabase.select")
async def supabase_select(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /{table} — select rows from a table using PostgREST query params."""
    table = config.get("table") or input_data.get("table")
    if not table:
        raise ValueError("supabase.select requires 'table'")
    params = {}
    select = config.get("select") or input_data.get("select")
    if select:
        params["select"] = select
    filters = config.get("filters") or input_data.get("filters") or {}
    params.update(filters)
    order = config.get("order") or input_data.get("order")
    if order:
        params["order"] = order
    limit = config.get("limit") or input_data.get("limit")
    if limit:
        params["limit"] = int(limit)
    offset = config.get("offset") or input_data.get("offset")
    if offset:
        params["offset"] = int(offset)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/{table}", params=params)
    return _check(r)


@register_node("supabase.insert")
async def supabase_insert(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /{table} — insert one or more rows into a table."""
    table = config.get("table") or input_data.get("table")
    data = config.get("data") or input_data.get("data")
    if not table:
        raise ValueError("supabase.insert requires 'table'")
    if data is None:
        raise ValueError("supabase.insert requires 'data'")
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/{table}", json=data)
    return _check(r)


@register_node("supabase.update")
async def supabase_update(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PATCH /{table} — update rows matching filter criteria."""
    table = config.get("table") or input_data.get("table")
    data = config.get("data") or input_data.get("data")
    if not table:
        raise ValueError("supabase.update requires 'table'")
    if data is None:
        raise ValueError("supabase.update requires 'data'")
    filters = config.get("filters") or input_data.get("filters") or {}
    async with await _client(credential_id, db) as client:
        r = await client.patch(f"/{table}", json=data, params=filters)
    return _check(r)


@register_node("supabase.delete")
async def supabase_delete(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /{table} — delete rows matching filter criteria."""
    table = config.get("table") or input_data.get("table")
    if not table:
        raise ValueError("supabase.delete requires 'table'")
    filters = config.get("filters") or input_data.get("filters") or {}
    if not filters:
        raise ValueError("supabase.delete requires at least one filter to prevent accidental full-table deletion")
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/{table}", params=filters)
    return _check(r)


@register_node("supabase.upsert")
async def supabase_upsert(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /{table} with Prefer: resolution=merge-duplicates — upsert rows."""
    table = config.get("table") or input_data.get("table")
    data = config.get("data") or input_data.get("data")
    if not table:
        raise ValueError("supabase.upsert requires 'table'")
    if data is None:
        raise ValueError("supabase.upsert requires 'data'")
    info = await _get_creds(credential_id, db)
    async with httpx.AsyncClient(
        base_url=f"{info['url']}/rest/v1",
        headers={
            "apikey": info["key"],
            "Authorization": f"Bearer {info['key']}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=representation",
        },
        timeout=30.0,
    ) as client:
        r = await client.post(f"/{table}", json=data)
    return _check(r)


@register_node("supabase.rpc")
async def supabase_rpc(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /rpc/{function_name} — call a PostgreSQL stored function."""
    function_name = config.get("function_name") or input_data.get("function_name")
    if not function_name:
        raise ValueError("supabase.rpc requires 'function_name'")
    params = config.get("params") or input_data.get("params") or {}
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/rpc/{function_name}", json=params)
    return _check(r)


@register_node("supabase.list_tables")
async def supabase_list_tables(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET / — list available tables via PostgREST root endpoint."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/")
    return _check(r)


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

@register_node("supabase.upload_file")
async def supabase_upload_file(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /object/{bucket_id}/{path} — upload a file to Supabase Storage."""
    bucket_id = config.get("bucket_id") or input_data.get("bucket_id")
    path = config.get("path") or input_data.get("path")
    file_content = config.get("file_content") or input_data.get("file_content")
    if not bucket_id or not path:
        raise ValueError("supabase.upload_file requires 'bucket_id' and 'path'")
    content_type = config.get("content_type") or input_data.get("content_type") or "application/octet-stream"
    async with await _storage_client(credential_id, db) as client:
        r = await client.post(
            f"/object/{bucket_id}/{path}",
            content=file_content or b"",
            headers={"Content-Type": content_type},
        )
    return _check(r)


@register_node("supabase.download_file")
async def supabase_download_file(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /object/{bucket_id}/{path} — download a file from Supabase Storage."""
    bucket_id = config.get("bucket_id") or input_data.get("bucket_id")
    path = config.get("path") or input_data.get("path")
    if not bucket_id or not path:
        raise ValueError("supabase.download_file requires 'bucket_id' and 'path'")
    async with await _storage_client(credential_id, db) as client:
        r = await client.get(f"/object/{bucket_id}/{path}")
    if not r.is_success:
        raise ValueError(f"Supabase Storage error {r.status_code}: {r.text}")
    return {"bucket_id": bucket_id, "path": path, "content": r.content.decode("utf-8", errors="replace")}


@register_node("supabase.list_files")
async def supabase_list_files(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /object/list/{bucket_id} — list files in a bucket/prefix."""
    bucket_id = config.get("bucket_id") or input_data.get("bucket_id")
    if not bucket_id:
        raise ValueError("supabase.list_files requires 'bucket_id'")
    body: dict = {}
    prefix = config.get("prefix") or input_data.get("prefix")
    if prefix:
        body["prefix"] = prefix
    limit = config.get("limit") or input_data.get("limit")
    if limit:
        body["limit"] = int(limit)
    async with await _storage_client(credential_id, db) as client:
        r = await client.post(f"/object/list/{bucket_id}", json=body,
                               headers={"Content-Type": "application/json"})
    return _check(r)


@register_node("supabase.delete_file")
async def supabase_delete_file(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /object/{bucket_id} — delete files from a bucket."""
    bucket_id = config.get("bucket_id") or input_data.get("bucket_id")
    prefixes = config.get("prefixes") or input_data.get("prefixes")
    if not bucket_id or not prefixes:
        raise ValueError("supabase.delete_file requires 'bucket_id' and 'prefixes'")
    async with await _storage_client(credential_id, db) as client:
        r = await client.delete(
            f"/object/{bucket_id}",
            json={"prefixes": prefixes},
            headers={"Content-Type": "application/json"},
        )
    return _check(r)


@register_node("supabase.create_signed_url")
async def supabase_create_signed_url(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /object/sign/{bucket_id}/{path} — create a signed URL for a file."""
    bucket_id = config.get("bucket_id") or input_data.get("bucket_id")
    path = config.get("path") or input_data.get("path")
    expires_in = config.get("expires_in") or input_data.get("expires_in") or 3600
    if not bucket_id or not path:
        raise ValueError("supabase.create_signed_url requires 'bucket_id' and 'path'")
    async with await _storage_client(credential_id, db) as client:
        r = await client.post(
            f"/object/sign/{bucket_id}/{path}",
            json={"expiresIn": int(expires_in)},
            headers={"Content-Type": "application/json"},
        )
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(credential_id: str, db) -> dict:
    """Test Supabase connection by querying the PostgREST root endpoint."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/")
    _check(r)
    return {"ok": True, "message": "Supabase connection successful"}
