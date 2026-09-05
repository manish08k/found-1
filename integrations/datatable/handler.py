"""DataTable integration — in-memory table operations on workflow data.

The table is passed through input_data["table"] as a list of dicts.
All operations return the (possibly modified) table alongside their results.
"""
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


@register_node("datatable.insert")
async def datatable_insert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Insert a new row into the in-memory table.

    config:
      columns — list of column names (used to validate/order the row)
      values  — dict mapping column names to values for the new row
    input_data:
      table   — current table state (list of dicts); defaults to empty list
    """
    table: list = list(input_data.get("table") or [])
    values: dict = config.get("values") or input_data.get("values") or {}
    if not values:
        raise ValueError("datatable.insert requires 'values' dict")
    row = dict(values)
    table.append(row)
    log.info("datatable.insert", row=row, total_rows=len(table))
    return {"table": table, "inserted_row": row, "total_rows": len(table)}


@register_node("datatable.lookup")
async def datatable_lookup(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Find all rows where a column matches a given value.

    config:
      lookup_column — column name to match against
      lookup_value  — value to match
    input_data:
      table         — current table state (list of dicts)
    """
    table: list = list(input_data.get("table") or [])
    lookup_column = config.get("lookup_column") or input_data.get("lookup_column")
    lookup_value = config.get("lookup_value") if "lookup_value" in config else input_data.get("lookup_value")
    if not lookup_column:
        raise ValueError("datatable.lookup requires 'lookup_column'")
    matched = [row for row in table if row.get(lookup_column) == lookup_value]
    log.info("datatable.lookup", column=lookup_column, value=lookup_value, matches=len(matched))
    return {"table": table, "results": matched, "count": len(matched)}


@register_node("datatable.update")
async def datatable_update(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update all rows matching a condition with new values.

    config:
      lookup_column — column name to match against
      lookup_value  — value to match
      update_data   — dict of column/value pairs to apply to matching rows
    input_data:
      table         — current table state (list of dicts)
    """
    table: list = list(input_data.get("table") or [])
    lookup_column = config.get("lookup_column") or input_data.get("lookup_column")
    lookup_value = config.get("lookup_value") if "lookup_value" in config else input_data.get("lookup_value")
    update_data: dict = config.get("update_data") or input_data.get("update_data") or {}
    if not lookup_column:
        raise ValueError("datatable.update requires 'lookup_column'")
    if not update_data:
        raise ValueError("datatable.update requires 'update_data' dict")
    updated_count = 0
    for row in table:
        if row.get(lookup_column) == lookup_value:
            row.update(update_data)
            updated_count += 1
    log.info("datatable.update", column=lookup_column, value=lookup_value, updated=updated_count)
    return {"table": table, "updated_count": updated_count}


@register_node("datatable.delete")
async def datatable_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete all rows matching a condition.

    config:
      lookup_column — column name to match against
      lookup_value  — value to match
    input_data:
      table         — current table state (list of dicts)
    """
    table: list = list(input_data.get("table") or [])
    lookup_column = config.get("lookup_column") or input_data.get("lookup_column")
    lookup_value = config.get("lookup_value") if "lookup_value" in config else input_data.get("lookup_value")
    if not lookup_column:
        raise ValueError("datatable.delete requires 'lookup_column'")
    original_len = len(table)
    table = [row for row in table if row.get(lookup_column) != lookup_value]
    deleted_count = original_len - len(table)
    log.info("datatable.delete", column=lookup_column, value=lookup_value, deleted=deleted_count)
    return {"table": table, "deleted_count": deleted_count, "total_rows": len(table)}


@register_node("datatable.get_all")
async def datatable_get_all(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Return all rows in the in-memory table.

    input_data:
      table — current table state (list of dicts)
    """
    table: list = list(input_data.get("table") or [])
    log.info("datatable.get_all", total_rows=len(table))
    return {"table": table, "rows": table, "total_rows": len(table)}
