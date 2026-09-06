"""DuckDB integration — in-process SQL analytics on local or in-memory databases."""
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _get_duckdb():
    try:
        import duckdb
        return duckdb
    except ImportError:
        raise ImportError(
            "duckdb is not installed. Install it with: pip install duckdb"
        )


@register_node("duckdb.execute_query")
async def duckdb_execute_query(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Execute a SQL query against a DuckDB database and return results.

    config:
      database   — path to the DuckDB file or ":memory:" (optional, default ":memory:")
      query      — SQL query to execute (required)
      parameters — list of positional parameters for the query (optional)
    """
    merged = {**config, **input_data}
    database = merged.get("database", ":memory:")
    query = merged.get("query")
    parameters = merged.get("parameters", [])

    if not query:
        raise ValueError("query is required for duckdb.execute_query")

    duckdb = _get_duckdb()

    conn = duckdb.connect(database)
    try:
        if parameters:
            relation = conn.execute(query, parameters)
        else:
            relation = conn.execute(query)

        columns = [desc[0] for desc in relation.description] if relation.description else []
        rows_raw = relation.fetchall()
        rows = [dict(zip(columns, row)) for row in rows_raw]
    finally:
        conn.close()

    log.info("duckdb.execute_query", database=database, row_count=len(rows))
    return {"rows": rows, "columns": columns, "row_count": len(rows)}


@register_node("duckdb.create_table")
async def duckdb_create_table(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Create a table in a DuckDB database.

    config:
      database     — path to the DuckDB file or ":memory:" (optional, default ":memory:")
      table_name   — name of the table to create (required)
      columns      — dict of column name to SQL type e.g. {"id": "INTEGER", "name": "VARCHAR"} (required)
      if_not_exists — add IF NOT EXISTS clause (optional, default True)
    """
    merged = {**config, **input_data}
    database = merged.get("database", ":memory:")
    table_name = merged.get("table_name")
    columns = merged.get("columns", {})
    if_not_exists = merged.get("if_not_exists", True)

    if not table_name or not columns:
        raise ValueError("table_name and columns are required for duckdb.create_table")

    col_defs = ", ".join(f'"{col}" {dtype}' for col, dtype in columns.items())
    exists_clause = "IF NOT EXISTS " if if_not_exists else ""
    query = f'CREATE TABLE {exists_clause}"{table_name}" ({col_defs})'

    duckdb = _get_duckdb()
    conn = duckdb.connect(database)
    try:
        conn.execute(query)
    finally:
        conn.close()

    log.info("duckdb.create_table", database=database, table_name=table_name)
    return {"success": True, "table_name": table_name, "query": query}


@register_node("duckdb.insert_data")
async def duckdb_insert_data(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Insert rows of data into a DuckDB table.

    config:
      database   — path to the DuckDB file or ":memory:" (optional, default ":memory:")
      table_name — name of the table to insert into (required)
      rows       — list of dicts representing rows to insert (required)
    """
    merged = {**config, **input_data}
    database = merged.get("database", ":memory:")
    table_name = merged.get("table_name")
    rows = merged.get("rows", [])

    if not table_name:
        raise ValueError("table_name is required for duckdb.insert_data")
    if not rows:
        raise ValueError("rows list is required for duckdb.insert_data")

    columns = list(rows[0].keys())
    col_names = ", ".join(f'"{c}"' for c in columns)
    placeholders = ", ".join("?" for _ in columns)
    query = f'INSERT INTO "{table_name}" ({col_names}) VALUES ({placeholders})'
    values = [[row.get(c) for c in columns] for row in rows]

    duckdb = _get_duckdb()
    conn = duckdb.connect(database)
    try:
        conn.executemany(query, values)
    finally:
        conn.close()

    log.info("duckdb.insert_data", database=database, table_name=table_name, row_count=len(rows))
    return {"success": True, "table_name": table_name, "rows_inserted": len(rows)}


@register_node("duckdb.export_csv")
async def duckdb_export_csv(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Export a DuckDB query result or table to a CSV file.

    config:
      database   — path to the DuckDB file or ":memory:" (optional, default ":memory:")
      query      — SQL SELECT query to export (required, or provide table_name)
      table_name — table to export (used if query is not provided)
      output_path — destination file path for the CSV (required)
      delimiter  — CSV delimiter character (optional, default ",")
      header     — include header row (optional, default True)
    """
    merged = {**config, **input_data}
    database = merged.get("database", ":memory:")
    query = merged.get("query")
    table_name = merged.get("table_name")
    output_path = merged.get("output_path")
    delimiter = merged.get("delimiter", ",")
    header = merged.get("header", True)

    if not output_path:
        raise ValueError("output_path is required for duckdb.export_csv")
    if not query and not table_name:
        raise ValueError("query or table_name is required for duckdb.export_csv")

    source = query if query else f'SELECT * FROM "{table_name}"'
    header_str = "TRUE" if header else "FALSE"
    export_query = (
        f"COPY ({source}) TO '{output_path}' "
        f"(FORMAT CSV, DELIMITER '{delimiter}', HEADER {header_str})"
    )

    duckdb = _get_duckdb()
    conn = duckdb.connect(database)
    try:
        conn.execute(export_query)
    finally:
        conn.close()

    log.info("duckdb.export_csv", database=database, output_path=output_path)
    return {"success": True, "output_path": output_path}
