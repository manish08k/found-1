"""
Coda.io collaborative docs integration.

Provides document listing, table browsing, and row management via the
Coda API v1.

Credential fields:
  - api_key : Coda API key (Bearer auth)

Base URL: https://coda.io/apis/v1/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://coda.io/apis/v1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Coda credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
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
        raise ValueError(f"Coda API error {r.status_code}: {detail}")


@register_node("coda.list_docs")
async def coda_list_docs(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all Coda docs accessible by the API key.

    Config:
      - query      : Optional search string to filter docs by name
      - limit      : Max number of docs to return (default 25)
      - page_token : Optional pagination token from a previous response
    """
    params: dict = {}
    query = config.get("query") or input_data.get("query")
    limit = int(config.get("limit") or input_data.get("limit", 25))
    page_token = config.get("page_token") or input_data.get("page_token")

    if query:
        params["query"] = query
    params["limit"] = limit
    if page_token:
        params["pageToken"] = page_token

    async with await _client(credential_id, db) as client:
        r = await client.get("/docs", params=params)
        _raise_for_status(r)
        data = r.json()

    return {
        "docs": data.get("items", []),
        "next_page_token": data.get("nextPageToken"),
        "href": data.get("href"),
    }


@register_node("coda.list_tables")
async def coda_list_tables(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List tables and views in a Coda doc.

    Config:
      - doc_id     : The Coda document ID (required)
      - table_type : Filter by 'table' or 'view' (optional)
      - limit      : Max number of results (default 25)
    """
    doc_id = config.get("doc_id") or input_data.get("doc_id")
    if not doc_id:
        raise ValueError("coda.list_tables requires 'doc_id'")

    params: dict = {}
    table_type = config.get("table_type") or input_data.get("table_type")
    limit = int(config.get("limit") or input_data.get("limit", 25))
    if table_type:
        params["tableTypes"] = table_type
    params["limit"] = limit

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/docs/{doc_id}/tables", params=params)
        _raise_for_status(r)
        data = r.json()

    return {
        "tables": data.get("items", []),
        "next_page_token": data.get("nextPageToken"),
        "doc_id": doc_id,
    }


@register_node("coda.list_rows")
async def coda_list_rows(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List rows in a Coda table.

    Config:
      - doc_id     : The Coda document ID (required)
      - table_id   : The table or view ID (required)
      - query      : Optional filter query string
      - limit      : Max rows to return (default 25, max 500)
      - page_token : Pagination token
      - use_column_names : Return column names instead of IDs (default True)
    """
    doc_id = config.get("doc_id") or input_data.get("doc_id")
    table_id = config.get("table_id") or input_data.get("table_id")
    if not doc_id or not table_id:
        raise ValueError("coda.list_rows requires 'doc_id' and 'table_id'")

    limit = min(int(config.get("limit") or input_data.get("limit", 25)), 500)
    query = config.get("query") or input_data.get("query")
    page_token = config.get("page_token") or input_data.get("page_token")
    use_column_names = bool(config.get("use_column_names", True) or input_data.get("use_column_names", True))

    params: dict = {"limit": limit, "useColumnNames": use_column_names}
    if query:
        params["query"] = query
    if page_token:
        params["pageToken"] = page_token

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/docs/{doc_id}/tables/{table_id}/rows", params=params)
        _raise_for_status(r)
        data = r.json()

    return {
        "rows": data.get("items", []),
        "next_page_token": data.get("nextPageToken"),
        "doc_id": doc_id,
        "table_id": table_id,
    }


@register_node("coda.insert_row")
async def coda_insert_row(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Insert one or more rows into a Coda table.

    Config:
      - doc_id     : The Coda document ID (required)
      - table_id   : The table ID (required)
      - rows        : List of dicts, each with a 'cells' list of {column, value} pairs (required)
                     OR a single flat dict of {column_name: value} pairs (convenience shorthand)
      - key_columns: Optional list of column IDs to use as upsert keys
    """
    doc_id = config.get("doc_id") or input_data.get("doc_id")
    table_id = config.get("table_id") or input_data.get("table_id")
    rows = config.get("rows") or input_data.get("rows")

    if not doc_id or not table_id:
        raise ValueError("coda.insert_row requires 'doc_id' and 'table_id'")
    if not rows:
        raise ValueError("coda.insert_row requires 'rows'")

    # Convenience: allow a single flat dict
    if isinstance(rows, dict):
        rows = [{"cells": [{"column": k, "value": v} for k, v in rows.items()]}]
    elif isinstance(rows, list) and rows and isinstance(rows[0], dict) and "cells" not in rows[0]:
        # List of flat dicts
        rows = [{"cells": [{"column": k, "value": v} for k, v in row.items()]} for row in rows]

    payload: dict = {"rows": rows}
    key_columns = config.get("key_columns") or input_data.get("key_columns")
    if key_columns:
        payload["keyColumns"] = key_columns

    async with await _client(credential_id, db) as client:
        r = await client.post(f"/docs/{doc_id}/tables/{table_id}/rows", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {
        "added_row_ids": data.get("addedRowIds", []),
        "request_id": data.get("requestId"),
        "doc_id": doc_id,
        "table_id": table_id,
    }


@register_node("coda.update_row")
async def coda_update_row(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Update a specific row in a Coda table.

    Config:
      - doc_id   : The Coda document ID (required)
      - table_id : The table ID (required)
      - row_id   : The row ID to update (required)
      - cells    : List of {column, value} pairs to update (required),
                   OR a flat dict of {column_name: value} pairs (convenience)
    """
    doc_id = config.get("doc_id") or input_data.get("doc_id")
    table_id = config.get("table_id") or input_data.get("table_id")
    row_id = config.get("row_id") or input_data.get("row_id")
    cells = config.get("cells") or input_data.get("cells")

    if not all([doc_id, table_id, row_id]):
        raise ValueError("coda.update_row requires 'doc_id', 'table_id', and 'row_id'")
    if not cells:
        raise ValueError("coda.update_row requires 'cells'")

    # Convenience: flat dict
    if isinstance(cells, dict):
        cells = [{"column": k, "value": v} for k, v in cells.items()]

    async with await _client(credential_id, db) as client:
        r = await client.put(
            f"/docs/{doc_id}/tables/{table_id}/rows/{row_id}",
            json={"row": {"cells": cells}},
        )
        _raise_for_status(r)
        data = r.json()

    return {
        "request_id": data.get("requestId"),
        "row_id": row_id,
        "doc_id": doc_id,
        "table_id": table_id,
    }


@register_node("coda.delete_row")
async def coda_delete_row(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Delete a row from a Coda table.

    Config:
      - doc_id   : The Coda document ID (required)
      - table_id : The table ID (required)
      - row_id   : The row ID to delete (required)
    """
    doc_id = config.get("doc_id") or input_data.get("doc_id")
    table_id = config.get("table_id") or input_data.get("table_id")
    row_id = config.get("row_id") or input_data.get("row_id")

    if not all([doc_id, table_id, row_id]):
        raise ValueError("coda.delete_row requires 'doc_id', 'table_id', and 'row_id'")

    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/docs/{doc_id}/tables/{table_id}/rows/{row_id}")
        _raise_for_status(r)
        data = r.json()

    return {
        "deleted": True,
        "request_id": data.get("requestId"),
        "row_id": row_id,
    }
