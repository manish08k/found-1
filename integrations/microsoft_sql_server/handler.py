"""Microsoft SQL Server integration — query and mutate data via pyodbc/aioodbc."""
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

try:
    import aioodbc
    _ASYNC_ODBC = True
except ImportError:
    _ASYNC_ODBC = False

try:
    import pyodbc as _pyodbc
    _SYNC_ODBC = True
except ImportError:
    _SYNC_ODBC = False


def _build_dsn(config: dict) -> str:
    """Build an ODBC connection string from config keys."""
    host = config.get("host", "localhost")
    port = config.get("port", 1433)
    database = config.get("database", "")
    username = config.get("username", "")
    password = config.get("password", "")
    driver = config.get("driver", "ODBC Driver 18 for SQL Server")
    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={host},{port};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        "TrustServerCertificate=yes;"
    )


async def _run_query(dsn: str, sql: str, params: tuple = ()) -> list[dict]:
    """Execute a SQL query and return rows as a list of dicts."""
    if _ASYNC_ODBC:
        async with await aioodbc.connect(dsn=dsn) as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql, params)
                if cursor.description:
                    cols = [d[0] for d in cursor.description]
                    rows = await cursor.fetchall()
                    return [dict(zip(cols, row)) for row in rows]
                await conn.commit()
                return []
    elif _SYNC_ODBC:
        import asyncio
        loop = asyncio.get_event_loop()

        def _sync():
            conn = _pyodbc.connect(dsn)
            try:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                if cursor.description:
                    cols = [d[0] for d in cursor.description]
                    rows = cursor.fetchall()
                    return [dict(zip(cols, row)) for row in rows]
                conn.commit()
                return []
            finally:
                conn.close()

        return await loop.run_in_executor(None, _sync)
    else:
        raise ImportError("Neither aioodbc nor pyodbc is installed. Install one to use SQL Server integration.")


@register_node("sql_server.execute_query")
async def sql_server_execute_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Execute a raw SQL query against Microsoft SQL Server.

    config/input_data:
      host     — SQL Server hostname or IP (required)
      port     — SQL Server port (optional, default 1433)
      database — database name (required)
      username — login username (required)
      password — login password (required)
      driver   — ODBC driver name (optional, default "ODBC Driver 18 for SQL Server")
      query    — SQL query string to execute (required)
      params   — list of query parameter values for parameterized queries (optional)
    """
    merged = {**config, **input_data}
    query = merged.get("query")
    if not query:
        raise ValueError("query is required for sql_server.execute_query")

    dsn = _build_dsn(merged)
    params = tuple(merged.get("params") or [])
    rows = await _run_query(dsn, query, params)

    log.info("sql_server.execute_query", row_count=len(rows), query=query[:80])
    return {"rows": rows, "count": len(rows)}


@register_node("sql_server.insert_row")
async def sql_server_insert_row(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Insert a single row into a SQL Server table.

    config/input_data:
      host     — SQL Server hostname or IP (required)
      port     — SQL Server port (optional, default 1433)
      database — database name (required)
      username — login username (required)
      password — login password (required)
      driver   — ODBC driver name (optional)
      table    — target table name (required)
      row      — dict mapping column names to values (required)
    """
    merged = {**config, **input_data}
    table = merged.get("table")
    row = merged.get("row")
    if not table:
        raise ValueError("table is required for sql_server.insert_row")
    if not row:
        raise ValueError("row is required for sql_server.insert_row")

    columns = list(row.keys())
    placeholders = ", ".join(["?"] * len(columns))
    col_list = ", ".join(f"[{c}]" for c in columns)
    sql = f"INSERT INTO [{table}] ({col_list}) VALUES ({placeholders})"
    params = tuple(row[c] for c in columns)

    dsn = _build_dsn(merged)
    await _run_query(dsn, sql, params)

    log.info("sql_server.insert_row", table=table, columns=columns)
    return {"inserted": True, "table": table, "columns": columns}


@register_node("sql_server.update_rows")
async def sql_server_update_rows(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update rows in a SQL Server table matching a WHERE clause.

    config/input_data:
      host        — SQL Server hostname or IP (required)
      port        — SQL Server port (optional, default 1433)
      database    — database name (required)
      username    — login username (required)
      password    — login password (required)
      driver      — ODBC driver name (optional)
      table       — target table name (required)
      set_values  — dict mapping column names to new values (required)
      where       — WHERE clause string, e.g. "id = ?" (required)
      where_params — list of parameter values for the WHERE clause (optional)
    """
    merged = {**config, **input_data}
    table = merged.get("table")
    set_values = merged.get("set_values")
    where = merged.get("where")
    if not table:
        raise ValueError("table is required for sql_server.update_rows")
    if not set_values:
        raise ValueError("set_values is required for sql_server.update_rows")
    if not where:
        raise ValueError("where is required for sql_server.update_rows")

    set_clause = ", ".join(f"[{c}] = ?" for c in set_values.keys())
    sql = f"UPDATE [{table}] SET {set_clause} WHERE {where}"
    params = tuple(set_values.values()) + tuple(merged.get("where_params") or [])

    dsn = _build_dsn(merged)
    await _run_query(dsn, sql, params)

    log.info("sql_server.update_rows", table=table, where=where)
    return {"updated": True, "table": table, "where": where}


@register_node("sql_server.delete_rows")
async def sql_server_delete_rows(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete rows from a SQL Server table matching a WHERE clause.

    config/input_data:
      host        — SQL Server hostname or IP (required)
      port        — SQL Server port (optional, default 1433)
      database    — database name (required)
      username    — login username (required)
      password    — login password (required)
      driver      — ODBC driver name (optional)
      table       — target table name (required)
      where       — WHERE clause string, e.g. "id = ?" (required)
      where_params — list of parameter values for the WHERE clause (optional)
    """
    merged = {**config, **input_data}
    table = merged.get("table")
    where = merged.get("where")
    if not table:
        raise ValueError("table is required for sql_server.delete_rows")
    if not where:
        raise ValueError("where is required for sql_server.delete_rows")

    sql = f"DELETE FROM [{table}] WHERE {where}"
    params = tuple(merged.get("where_params") or [])

    dsn = _build_dsn(merged)
    await _run_query(dsn, sql, params)

    log.info("sql_server.delete_rows", table=table, where=where)
    return {"deleted": True, "table": table, "where": where}
