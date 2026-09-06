"""Retable integration — workspaces, tables, and row management."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

RETABLE_BASE = "https://api.retable.io/v1"


def _retable_headers(api_key: str) -> dict:
    return {"ApiKey": api_key, "Content-Type": "application/json"}


@register_node("retable.list_workspaces")
async def retable_list_workspaces(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all workspaces available to the authenticated Retable user.

    config:
      api_key — Retable API key (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for retable.list_workspaces")

    async with httpx.AsyncClient(base_url=RETABLE_BASE, timeout=30) as client:
        r = await client.get("/workspace", headers=_retable_headers(api_key))
        r.raise_for_status()
        data = r.json()

    workspaces = data.get("data", data) if isinstance(data, dict) else data
    log.info("retable.list_workspaces", count=len(workspaces) if isinstance(workspaces, list) else 1)
    return {"workspaces": workspaces}


@register_node("retable.list_tables")
async def retable_list_tables(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List tables within a Retable project.

    config:
      api_key    — Retable API key (required)
      project_id — project ID to list tables from (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    project_id = merged.get("project_id")
    if not api_key or not project_id:
        raise ValueError("api_key and project_id are required for retable.list_tables")

    async with httpx.AsyncClient(base_url=RETABLE_BASE, timeout=30) as client:
        r = await client.get(f"/project/{project_id}", headers=_retable_headers(api_key))
        r.raise_for_status()
        data = r.json()

    tables = data.get("data", {}).get("tables", data.get("tables", []))
    log.info("retable.list_tables", project_id=project_id, count=len(tables))
    return {"tables": tables, "count": len(tables), "project_id": project_id}


@register_node("retable.get_rows")
async def retable_get_rows(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get rows from a Retable table.

    config:
      api_key   — Retable API key (required)
      table_id  — table ID to get rows from (required)
      page      — page number (optional, default 1)
      size      — results per page (optional, default 50)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    table_id = merged.get("table_id")
    if not api_key or not table_id:
        raise ValueError("api_key and table_id are required for retable.get_rows")

    params: dict = {"page": merged.get("page", 1), "size": merged.get("size", 50)}

    async with httpx.AsyncClient(base_url=RETABLE_BASE, timeout=30) as client:
        r = await client.get(f"/retable/{table_id}/data", headers=_retable_headers(api_key), params=params)
        r.raise_for_status()
        data = r.json()

    rows = data.get("data", {}).get("rows", data.get("rows", []))
    log.info("retable.get_rows", table_id=table_id, count=len(rows))
    return {"rows": rows, "count": len(rows), "table_id": table_id}


@register_node("retable.create_row")
async def retable_create_row(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new row in a Retable table.

    config:
      api_key  — Retable API key (required)
      table_id — table ID (required)
      data     — list of column value dicts with column_id and value (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    table_id = merged.get("table_id")
    row_data = merged.get("data", [])
    if not api_key or not table_id:
        raise ValueError("api_key and table_id are required for retable.create_row")

    payload = {"data": row_data}

    async with httpx.AsyncClient(base_url=RETABLE_BASE, timeout=30) as client:
        r = await client.post(
            f"/retable/{table_id}/data",
            headers=_retable_headers(api_key),
            json=payload,
        )
        r.raise_for_status()
        data = r.json()

    log.info("retable.create_row", table_id=table_id)
    return {"result": data, "table_id": table_id}


@register_node("retable.update_row")
async def retable_update_row(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update an existing row in a Retable table.

    config:
      api_key  — Retable API key (required)
      table_id — table ID (required)
      row_id   — row ID to update (required)
      data     — list of column value dicts with column_id and value (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    table_id = merged.get("table_id")
    row_id = merged.get("row_id")
    row_data = merged.get("data", [])
    if not api_key or not table_id or not row_id:
        raise ValueError("api_key, table_id, and row_id are required for retable.update_row")

    payload = {"data": row_data}

    async with httpx.AsyncClient(base_url=RETABLE_BASE, timeout=30) as client:
        r = await client.put(
            f"/retable/{table_id}/data/{row_id}",
            headers=_retable_headers(api_key),
            json=payload,
        )
        r.raise_for_status()
        data = r.json()

    log.info("retable.update_row", table_id=table_id, row_id=row_id)
    return {"result": data, "table_id": table_id, "row_id": row_id}


@register_node("retable.delete_row")
async def retable_delete_row(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete a row from a Retable table.

    config:
      api_key  — Retable API key (required)
      table_id — table ID (required)
      row_id   — row ID to delete (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    table_id = merged.get("table_id")
    row_id = merged.get("row_id")
    if not api_key or not table_id or not row_id:
        raise ValueError("api_key, table_id, and row_id are required for retable.delete_row")

    async with httpx.AsyncClient(base_url=RETABLE_BASE, timeout=30) as client:
        r = await client.delete(
            f"/retable/{table_id}/data/{row_id}",
            headers=_retable_headers(api_key),
        )
        r.raise_for_status()

    log.info("retable.delete_row", table_id=table_id, row_id=row_id)
    return {"success": True, "table_id": table_id, "row_id": row_id}
