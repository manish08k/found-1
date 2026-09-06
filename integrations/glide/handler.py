"""Glide integration — read and write data in Glide app tables."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

GLIDE_BASE = "https://api.glideapp.io/api/function"


def _glide_headers(api_token: str) -> dict:
    return {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}


@register_node("glide.get_table")
async def glide_get_table(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Retrieve the schema/metadata of a Glide table.

    config:
      api_token  — Glide API token (required)
      app_id     — Glide application ID (required)
      table_name — name of the table (required)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    app_id = merged.get("app_id")
    table_name = merged.get("table_name")

    if not app_id or not table_name:
        raise ValueError("app_id and table_name are required for glide.get_table")

    payload = {
        "appID": app_id,
        "queries": [{"tableName": table_name, "utc": True}],
    }

    async with httpx.AsyncClient(base_url=GLIDE_BASE, timeout=30) as client:
        r = await client.post(
            "/queryTables", headers=_glide_headers(api_token), json=payload
        )
        r.raise_for_status()
        data = r.json()

    log.info("glide.get_table", app_id=app_id, table_name=table_name)
    return {"table": data, "app_id": app_id, "table_name": table_name}


@register_node("glide.list_rows")
async def glide_list_rows(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List rows from a Glide table.

    config:
      api_token  — Glide API token (required)
      app_id     — Glide application ID (required)
      table_name — name of the table (required)
      limit      — max rows to return (optional)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    app_id = merged.get("app_id")
    table_name = merged.get("table_name")

    if not app_id or not table_name:
        raise ValueError("app_id and table_name are required for glide.list_rows")

    query: dict = {"tableName": table_name, "utc": True}
    if merged.get("limit"):
        query["limit"] = merged["limit"]

    payload = {"appID": app_id, "queries": [query]}

    async with httpx.AsyncClient(base_url=GLIDE_BASE, timeout=30) as client:
        r = await client.post(
            "/queryTables", headers=_glide_headers(api_token), json=payload
        )
        r.raise_for_status()
        data = r.json()

    rows = data[0].get("rows", []) if isinstance(data, list) and data else []
    log.info("glide.list_rows", app_id=app_id, table_name=table_name, count=len(rows))
    return {"rows": rows, "count": len(rows)}


@register_node("glide.add_row")
async def glide_add_row(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Add a new row to a Glide table.

    config:
      api_token  — Glide API token (required)
      app_id     — Glide application ID (required)
      table_name — name of the table (required)
      row        — dict of column name to value (required)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    app_id = merged.get("app_id")
    table_name = merged.get("table_name")
    row = merged.get("row", {})

    if not app_id or not table_name:
        raise ValueError("app_id and table_name are required for glide.add_row")
    if not row:
        raise ValueError("row dict is required for glide.add_row")

    payload = {
        "appID": app_id,
        "mutations": [
            {
                "kind": "add-row-to-table",
                "tableName": table_name,
                "columnValues": row,
            }
        ],
    }

    async with httpx.AsyncClient(base_url=GLIDE_BASE, timeout=30) as client:
        r = await client.post(
            "/mutateTables", headers=_glide_headers(api_token), json=payload
        )
        r.raise_for_status()
        data = r.json()

    log.info("glide.add_row", app_id=app_id, table_name=table_name)
    return {"result": data, "app_id": app_id, "table_name": table_name}


@register_node("glide.update_row")
async def glide_update_row(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update an existing row in a Glide table.

    config:
      api_token  — Glide API token (required)
      app_id     — Glide application ID (required)
      table_name — name of the table (required)
      row_id     — ID of the row to update (required)
      row        — dict of column name to new value (required)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    app_id = merged.get("app_id")
    table_name = merged.get("table_name")
    row_id = merged.get("row_id")
    row = merged.get("row", {})

    if not app_id or not table_name or not row_id:
        raise ValueError("app_id, table_name, and row_id are required for glide.update_row")
    if not row:
        raise ValueError("row dict is required for glide.update_row")

    payload = {
        "appID": app_id,
        "mutations": [
            {
                "kind": "set-columns-in-row",
                "tableName": table_name,
                "rowID": row_id,
                "columnValues": row,
            }
        ],
    }

    async with httpx.AsyncClient(base_url=GLIDE_BASE, timeout=30) as client:
        r = await client.post(
            "/mutateTables", headers=_glide_headers(api_token), json=payload
        )
        r.raise_for_status()
        data = r.json()

    log.info("glide.update_row", app_id=app_id, table_name=table_name, row_id=row_id)
    return {"result": data, "row_id": row_id}


@register_node("glide.delete_row")
async def glide_delete_row(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete a row from a Glide table.

    config:
      api_token  — Glide API token (required)
      app_id     — Glide application ID (required)
      table_name — name of the table (required)
      row_id     — ID of the row to delete (required)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    app_id = merged.get("app_id")
    table_name = merged.get("table_name")
    row_id = merged.get("row_id")

    if not app_id or not table_name or not row_id:
        raise ValueError("app_id, table_name, and row_id are required for glide.delete_row")

    payload = {
        "appID": app_id,
        "mutations": [
            {
                "kind": "delete-row",
                "tableName": table_name,
                "rowID": row_id,
            }
        ],
    }

    async with httpx.AsyncClient(base_url=GLIDE_BASE, timeout=30) as client:
        r = await client.post(
            "/mutateTables", headers=_glide_headers(api_token), json=payload
        )
        r.raise_for_status()
        data = r.json()

    log.info("glide.delete_row", app_id=app_id, table_name=table_name, row_id=row_id)
    return {"result": data, "row_id": row_id, "deleted": True}
