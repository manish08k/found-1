"""MySQL integration using aiomysql for async database operations."""
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _get_conn_params(merged: dict) -> dict:
    """Extract MySQL connection parameters from merged config/input_data."""
    return {
        "host": merged.get("host") or "localhost",
        "port": int(merged.get("port", 3306)),
        "user": merged.get("user") or "",
        "password": merged.get("password") or "",
        "db": merged.get("database") or "",
    }


@register_node("mysql.execute_query")
async def execute_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Execute a raw SQL query.

    config/input_data:
      host       — MySQL host (default localhost)
      port       — MySQL port (default 3306)
      user       — database user (required)
      password   — database password (required)
      database   — database name (required)
      query      — SQL query to execute (required)
      parameters — list of positional parameters (optional)
    """
    try:
        import aiomysql
    except ImportError:
        raise ImportError(
            "aiomysql is required for mysql operations. "
            "Install it with: pip install aiomysql"
        )

    merged = {**config, **input_data}
    conn_params = _get_conn_params(merged)
    query = merged.get("query") or ""
    parameters = merged.get("parameters") or ()

    if not query:
        raise ValueError("query is required for mysql.execute_query")

    async with aiomysql.connect(**conn_params) as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(query, parameters or ())
            rows = await cursor.fetchall()
            rowcount = cursor.rowcount

    rows = [dict(r) for r in rows]
    log.info("mysql.execute_query", rowcount=rowcount, rows_returned=len(rows))
    return {"rows": rows, "rowcount": rowcount}


@register_node("mysql.insert")
async def insert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Insert a row into a MySQL table.

    config/input_data:
      host     — MySQL host (default localhost)
      port     — MySQL port (default 3306)
      user     — database user (required)
      password — database password (required)
      database — database name (required)
      table    — target table name (required)
      data     — dict of column->value to insert (required)
    """
    try:
        import aiomysql
    except ImportError:
        raise ImportError(
            "aiomysql is required for mysql operations. "
            "Install it with: pip install aiomysql"
        )

    merged = {**config, **input_data}
    conn_params = _get_conn_params(merged)
    table = merged.get("table") or ""
    data = merged.get("data") or {}

    if not table:
        raise ValueError("table is required for mysql.insert")
    if not data:
        raise ValueError("data is required for mysql.insert")

    columns = list(data.keys())
    placeholders = ", ".join(["%s"] * len(columns))
    col_names = ", ".join(f"`{c}`" for c in columns)
    values = [data[c] for c in columns]
    query = f"INSERT INTO `{table}` ({col_names}) VALUES ({placeholders})"

    async with aiomysql.connect(**conn_params) as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(query, values)
            insert_id = cursor.lastrowid
            rowcount = cursor.rowcount
        await conn.commit()

    log.info("mysql.insert", table=table, insert_id=insert_id)
    return {"insert_id": insert_id, "rowcount": rowcount}


@register_node("mysql.update")
async def update(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update rows in a MySQL table.

    config/input_data:
      host     — MySQL host (default localhost)
      port     — MySQL port (default 3306)
      user     — database user (required)
      password — database password (required)
      database — database name (required)
      table    — target table name (required)
      data     — dict of column->value to update (required)
      where    — dict of column->value for WHERE clause (required)
    """
    try:
        import aiomysql
    except ImportError:
        raise ImportError(
            "aiomysql is required for mysql operations. "
            "Install it with: pip install aiomysql"
        )

    merged = {**config, **input_data}
    conn_params = _get_conn_params(merged)
    table = merged.get("table") or ""
    data = merged.get("data") or {}
    where = merged.get("where") or {}

    if not table:
        raise ValueError("table is required for mysql.update")
    if not data:
        raise ValueError("data is required for mysql.update")
    if not where:
        raise ValueError("where is required for mysql.update")

    set_clause = ", ".join(f"`{c}` = %s" for c in data.keys())
    where_clause = " AND ".join(f"`{c}` = %s" for c in where.keys())
    values = list(data.values()) + list(where.values())
    query = f"UPDATE `{table}` SET {set_clause} WHERE {where_clause}"

    async with aiomysql.connect(**conn_params) as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(query, values)
            rowcount = cursor.rowcount
        await conn.commit()

    log.info("mysql.update", table=table, rowcount=rowcount)
    return {"rowcount": rowcount}


@register_node("mysql.delete")
async def delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete rows from a MySQL table.

    config/input_data:
      host     — MySQL host (default localhost)
      port     — MySQL port (default 3306)
      user     — database user (required)
      password — database password (required)
      database — database name (required)
      table    — target table name (required)
      where    — dict of column->value for WHERE clause (required)
    """
    try:
        import aiomysql
    except ImportError:
        raise ImportError(
            "aiomysql is required for mysql operations. "
            "Install it with: pip install aiomysql"
        )

    merged = {**config, **input_data}
    conn_params = _get_conn_params(merged)
    table = merged.get("table") or ""
    where = merged.get("where") or {}

    if not table:
        raise ValueError("table is required for mysql.delete")
    if not where:
        raise ValueError("where is required for mysql.delete")

    where_clause = " AND ".join(f"`{c}` = %s" for c in where.keys())
    values = list(where.values())
    query = f"DELETE FROM `{table}` WHERE {where_clause}"

    async with aiomysql.connect(**conn_params) as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(query, values)
            rowcount = cursor.rowcount
        await conn.commit()

    log.info("mysql.delete", table=table, rowcount=rowcount)
    return {"rowcount": rowcount}
