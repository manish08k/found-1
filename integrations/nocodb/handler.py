"""
NocoDB integration.

Credential fields:
  - api_key: NocoDB API token (xc-token header)
  - base_url: NocoDB instance URL (e.g. https://app.nocodb.com)

Auth: xc-token header
Base URL: {base_url}/api/v1
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    base_url = creds.get("base_url", "https://app.nocodb.com")
    if not api_key:
        raise ValueError("NocoDB credential is missing 'api_key'")
    return httpx.AsyncClient(
        base_url=f"{base_url.rstrip('/')}/api/v1",
        headers={
            "xc-token": api_key,
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
        raise ValueError(f"NocoDB API error {r.status_code}: {detail}")
    try:
        return r.json()
    except Exception:
        return {"raw": r.text}


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@register_node("nocodb.list_bases")
async def nocodb_list_bases(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /db/meta/projects — list all bases/projects."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/db/meta/projects/")
    return _check(r)


@register_node("nocodb.list_tables")
async def nocodb_list_tables(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /db/meta/projects/{base_id}/tables — list tables in a base."""
    base_id = config.get("base_id") or input_data.get("base_id")
    if not base_id:
        raise ValueError("nocodb.list_tables requires 'base_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/db/meta/projects/{base_id}/tables")
    return _check(r)


@register_node("nocodb.list_views")
async def nocodb_list_views(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /db/meta/tables/{table_id}/views — list views for a table."""
    table_id = config.get("table_id") or input_data.get("table_id")
    if not table_id:
        raise ValueError("nocodb.list_views requires 'table_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/db/meta/tables/{table_id}/views")
    return _check(r)


@register_node("nocodb.list_rows")
async def nocodb_list_rows(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /db/data/noco/{base_id}/{table_id} — list rows in a table."""
    base_id = config.get("base_id") or input_data.get("base_id")
    table_id = config.get("table_id") or input_data.get("table_id")
    if not base_id or not table_id:
        raise ValueError("nocodb.list_rows requires 'base_id' and 'table_id'")
    params: dict = {}
    limit = config.get("limit") or input_data.get("limit")
    if limit:
        params["limit"] = int(limit)
    offset = config.get("offset") or input_data.get("offset")
    if offset:
        params["offset"] = int(offset)
    where = config.get("where") or input_data.get("where")
    if where:
        params["where"] = where
    sort = config.get("sort") or input_data.get("sort")
    if sort:
        params["sort"] = sort
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/db/data/noco/{base_id}/{table_id}", params=params)
    return _check(r)


@register_node("nocodb.get_row")
async def nocodb_get_row(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /db/data/noco/{base_id}/{table_id}/{row_id} — get a single row."""
    base_id = config.get("base_id") or input_data.get("base_id")
    table_id = config.get("table_id") or input_data.get("table_id")
    row_id = config.get("row_id") or input_data.get("row_id")
    if not base_id or not table_id or not row_id:
        raise ValueError("nocodb.get_row requires 'base_id', 'table_id', and 'row_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/db/data/noco/{base_id}/{table_id}/{row_id}")
    return _check(r)


@register_node("nocodb.create_row")
async def nocodb_create_row(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /db/data/noco/{base_id}/{table_id} — create a row."""
    base_id = config.get("base_id") or input_data.get("base_id")
    table_id = config.get("table_id") or input_data.get("table_id")
    data = config.get("data") or input_data.get("data")
    if not base_id or not table_id:
        raise ValueError("nocodb.create_row requires 'base_id' and 'table_id'")
    if not data:
        raise ValueError("nocodb.create_row requires 'data'")
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/db/data/noco/{base_id}/{table_id}", json=data)
    return _check(r)


@register_node("nocodb.update_row")
async def nocodb_update_row(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PATCH /db/data/noco/{base_id}/{table_id}/{row_id} — update a row."""
    base_id = config.get("base_id") or input_data.get("base_id")
    table_id = config.get("table_id") or input_data.get("table_id")
    row_id = config.get("row_id") or input_data.get("row_id")
    data = config.get("data") or input_data.get("data")
    if not base_id or not table_id or not row_id:
        raise ValueError("nocodb.update_row requires 'base_id', 'table_id', and 'row_id'")
    if not data:
        raise ValueError("nocodb.update_row requires 'data'")
    async with await _client(credential_id, db) as client:
        r = await client.patch(f"/db/data/noco/{base_id}/{table_id}/{row_id}", json=data)
    return _check(r)


@register_node("nocodb.delete_row")
async def nocodb_delete_row(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /db/data/noco/{base_id}/{table_id}/{row_id} — delete a row."""
    base_id = config.get("base_id") or input_data.get("base_id")
    table_id = config.get("table_id") or input_data.get("table_id")
    row_id = config.get("row_id") or input_data.get("row_id")
    if not base_id or not table_id or not row_id:
        raise ValueError("nocodb.delete_row requires 'base_id', 'table_id', and 'row_id'")
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/db/data/noco/{base_id}/{table_id}/{row_id}")
    return _check(r)


@register_node("nocodb.bulk_create_rows")
async def nocodb_bulk_create_rows(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /db/data/noco/{base_id}/{table_id}/bulk — bulk create rows."""
    base_id = config.get("base_id") or input_data.get("base_id")
    table_id = config.get("table_id") or input_data.get("table_id")
    rows = config.get("rows") or input_data.get("rows")
    if not base_id or not table_id:
        raise ValueError("nocodb.bulk_create_rows requires 'base_id' and 'table_id'")
    if not rows:
        raise ValueError("nocodb.bulk_create_rows requires 'rows'")
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/db/data/noco/{base_id}/{table_id}/bulk", json=rows)
    return _check(r)


@register_node("nocodb.search_rows")
async def nocodb_search_rows(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /db/data/noco/{base_id}/{table_id} with where filter — search rows."""
    base_id = config.get("base_id") or input_data.get("base_id")
    table_id = config.get("table_id") or input_data.get("table_id")
    where = config.get("where") or input_data.get("where")
    if not base_id or not table_id:
        raise ValueError("nocodb.search_rows requires 'base_id' and 'table_id'")
    if not where:
        raise ValueError("nocodb.search_rows requires 'where'")
    params: dict = {"where": where}
    limit = config.get("limit") or input_data.get("limit")
    if limit:
        params["limit"] = int(limit)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/db/data/noco/{base_id}/{table_id}", params=params)
    return _check(r)


async def test_connection(credential_id: str, db) -> dict:
    """Test NocoDB connection by listing bases."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/db/meta/projects/")
    _check(r)
    return {"ok": True}
