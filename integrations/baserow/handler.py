"""
Baserow open-source no-code database integration.

Provides row management (list, create, update, delete, search) on any
Baserow table via the Baserow REST API.

Credential fields:
  - token : Baserow Database Token (created in Account Settings > Database tokens)

Auth: Token {token} via Authorization header.
Base URL: https://api.baserow.io/api/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.baserow.io/api"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    token = creds.get("token")
    if not token:
        raise ValueError("Baserow credential missing 'token'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Token {token}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Baserow API error {r.status_code}: {detail}")


@register_node("baserow.list_rows")
async def br_list_rows(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    List rows from a Baserow table.

    Params:
      - table_id (required): Numeric ID of the table.
      - page: Page number (default 1).
      - size: Rows per page (max 200, default 100).
      - order_by: Field name to order by, prefix with '-' for descending.
      - search: Full-text search term across all fields.
      - filter_field: Field name to filter on.
      - filter_value: Value to filter by.
      - filter_type: 'equal', 'contains', 'higher_than', etc. (default 'equal').
      - view_id: Restrict results to a specific view.
    """
    table_id = config.get("table_id") or input_data.get("table_id")
    if not table_id:
        raise ValueError("baserow.list_rows requires 'table_id'")

    page = int(config.get("page") or input_data.get("page", 1))
    size = min(int(config.get("size") or input_data.get("size", 100)), 200)
    order_by = config.get("order_by") or input_data.get("order_by")
    search = config.get("search") or input_data.get("search")
    view_id = config.get("view_id") or input_data.get("view_id")
    filter_field = config.get("filter_field") or input_data.get("filter_field")
    filter_value = config.get("filter_value") or input_data.get("filter_value")
    filter_type = config.get("filter_type") or input_data.get("filter_type", "equal")

    params: dict = {"page": page, "size": size}
    if order_by:
        params["order_by"] = order_by
    if search:
        params["search"] = search
    if view_id:
        params["view_id"] = view_id
    if filter_field and filter_value is not None:
        params[f"filter__{filter_field}__{filter_type}"] = filter_value

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/database/rows/table/{table_id}/", params=params)
        _raise_for_status(r)
        data = r.json()

    log.info("baserow.list_rows", table_id=table_id, count=data.get("count", 0))
    return {
        "rows": data.get("results", []),
        "count": data.get("count", 0),
        "next": data.get("next"),
        "previous": data.get("previous"),
    }


@register_node("baserow.create_row")
async def br_create_row(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Create a new row in a Baserow table.

    Params:
      - table_id (required): Numeric ID of the table.
      - fields (dict, required): Key-value pairs mapping field names to values.
        Field names must match column names in Baserow (or use field IDs like 'field_123').
      - before_id: Insert the row before this row ID.
    """
    table_id = config.get("table_id") or input_data.get("table_id")
    fields = config.get("fields") or input_data.get("fields")
    if not table_id:
        raise ValueError("baserow.create_row requires 'table_id'")
    if not fields:
        raise ValueError("baserow.create_row requires 'fields' dict")
    if isinstance(fields, str):
        import json
        fields = json.loads(fields)

    params: dict = {"user_field_names": "true"}
    before_id = config.get("before_id") or input_data.get("before_id")
    if before_id:
        params["before_id"] = before_id

    async with await _client(credential_id, db) as client:
        r = await client.post(
            f"/database/rows/table/{table_id}/",
            json=fields,
            params=params,
        )
        _raise_for_status(r)
        data = r.json()

    log.info("baserow.create_row", table_id=table_id, row_id=data.get("id"))
    return {"row": data, "id": data.get("id")}


@register_node("baserow.update_row")
async def br_update_row(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Update an existing row in a Baserow table.

    Params:
      - table_id (required): Numeric ID of the table.
      - row_id (required): ID of the row to update.
      - fields (dict, required): Key-value pairs of fields to update.
    """
    table_id = config.get("table_id") or input_data.get("table_id")
    row_id = config.get("row_id") or input_data.get("row_id")
    fields = config.get("fields") or input_data.get("fields")
    if not table_id:
        raise ValueError("baserow.update_row requires 'table_id'")
    if not row_id:
        raise ValueError("baserow.update_row requires 'row_id'")
    if not fields:
        raise ValueError("baserow.update_row requires 'fields' dict")
    if isinstance(fields, str):
        import json
        fields = json.loads(fields)

    params: dict = {"user_field_names": "true"}

    async with await _client(credential_id, db) as client:
        r = await client.patch(
            f"/database/rows/table/{table_id}/{row_id}/",
            json=fields,
            params=params,
        )
        _raise_for_status(r)
        data = r.json()

    log.info("baserow.update_row", table_id=table_id, row_id=row_id)
    return {"row": data, "id": data.get("id")}


@register_node("baserow.delete_row")
async def br_delete_row(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Delete a row from a Baserow table.

    Params:
      - table_id (required): Numeric ID of the table.
      - row_id (required): ID of the row to delete.
    """
    table_id = config.get("table_id") or input_data.get("table_id")
    row_id = config.get("row_id") or input_data.get("row_id")
    if not table_id:
        raise ValueError("baserow.delete_row requires 'table_id'")
    if not row_id:
        raise ValueError("baserow.delete_row requires 'row_id'")

    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/database/rows/table/{table_id}/{row_id}/")
        _raise_for_status(r)

    log.info("baserow.delete_row", table_id=table_id, row_id=row_id)
    return {"deleted": True, "table_id": table_id, "row_id": row_id}


@register_node("baserow.search_rows")
async def br_search_rows(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Full-text search rows across all fields in a Baserow table.

    Params:
      - table_id (required): Numeric ID of the table.
      - query (required): Search term.
      - page: Page number (default 1).
      - size: Rows per page (max 200, default 50).
    """
    table_id = config.get("table_id") or input_data.get("table_id")
    query = config.get("query") or input_data.get("query")
    if not table_id:
        raise ValueError("baserow.search_rows requires 'table_id'")
    if not query:
        raise ValueError("baserow.search_rows requires 'query'")

    page = int(config.get("page") or input_data.get("page", 1))
    size = min(int(config.get("size") or input_data.get("size", 50)), 200)

    params = {"search": query, "page": page, "size": size, "user_field_names": "true"}

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/database/rows/table/{table_id}/", params=params)
        _raise_for_status(r)
        data = r.json()

    log.info("baserow.search_rows", table_id=table_id, query=query, count=data.get("count", 0))
    return {
        "rows": data.get("results", []),
        "count": data.get("count", 0),
        "query": query,
    }


@register_node("baserow.get_row")
async def br_get_row(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Retrieve a single row by ID.

    Params:
      - table_id (required): Numeric ID of the table.
      - row_id (required): ID of the row to retrieve.
    """
    table_id = config.get("table_id") or input_data.get("table_id")
    row_id = config.get("row_id") or input_data.get("row_id")
    if not table_id:
        raise ValueError("baserow.get_row requires 'table_id'")
    if not row_id:
        raise ValueError("baserow.get_row requires 'row_id'")

    params = {"user_field_names": "true"}

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/database/rows/table/{table_id}/{row_id}/", params=params)
        _raise_for_status(r)
        data = r.json()

    return {"row": data, "id": data.get("id")}
