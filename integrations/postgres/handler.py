"""PostgreSQL integration — execute queries, insert, update, delete rows."""
import asyncpg
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _build_conn_params(config: dict) -> dict:
    return {
        "host": config.get("host", "localhost"),
        "port": int(config.get("port", 5432)),
        "user": config.get("user", "postgres"),
        "password": config.get("password", ""),
        "database": config.get("database", "postgres"),
    }


@register_node("postgres.execute_query")
async def pg_execute_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Run an arbitrary SQL query with optional positional parameters.

    config/input_data:
      host, port, user, password, database — connection params
      query      — SQL string (use $1, $2, … placeholders)
      parameters — list of parameter values (default [])
    """
    merged = {**config, **input_data}
    query = merged.get("query")
    if not query:
        raise ValueError("query is required for postgres.execute_query")

    params = merged.get("parameters", [])
    conn_params = _build_conn_params(merged)

    conn = await asyncpg.connect(**conn_params)
    try:
        rows = await conn.fetch(query, *params)
        row_dicts = [dict(r) for r in rows]
        log.info("postgres.execute_query", rowcount=len(row_dicts))
        return {"rows": row_dicts, "rowcount": len(row_dicts)}
    finally:
        await conn.close()


@register_node("postgres.insert")
async def pg_insert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """INSERT a single row into a table.

    config/input_data:
      host, port, user, password, database — connection params
      table — target table name
      data  — dict of {column: value}
    """
    merged = {**config, **input_data}
    table = merged.get("table")
    data = merged.get("data", {})
    if not table:
        raise ValueError("table is required for postgres.insert")
    if not data:
        raise ValueError("data is required for postgres.insert")

    columns = list(data.keys())
    values = [data[c] for c in columns]
    placeholders = ", ".join(f"${i + 1}" for i in range(len(columns)))
    col_list = ", ".join(columns)
    query = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"

    conn_params = _build_conn_params(merged)
    conn = await asyncpg.connect(**conn_params)
    try:
        result = await conn.execute(query, *values)
        # result is a string like "INSERT 0 1"
        rowcount = int(result.split()[-1]) if result else 1
        log.info("postgres.insert", table=table, rowcount=rowcount)
        return {"rowcount": rowcount}
    finally:
        await conn.close()


@register_node("postgres.update")
async def pg_update(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """UPDATE rows in a table matching WHERE conditions.

    config/input_data:
      host, port, user, password, database — connection params
      table — target table name
      data  — dict of {column: new_value}
      where — dict of {column: value} for the WHERE clause (AND-joined)
    """
    merged = {**config, **input_data}
    table = merged.get("table")
    data = merged.get("data", {})
    where = merged.get("where", {})
    if not table:
        raise ValueError("table is required for postgres.update")
    if not data:
        raise ValueError("data is required for postgres.update")

    set_columns = list(data.keys())
    set_values = [data[c] for c in set_columns]
    where_columns = list(where.keys())
    where_values = [where[c] for c in where_columns]

    all_values = set_values + where_values
    set_clause = ", ".join(f"{c} = ${i + 1}" for i, c in enumerate(set_columns))
    where_clause = " AND ".join(
        f"{c} = ${len(set_columns) + i + 1}" for i, c in enumerate(where_columns)
    )

    query = f"UPDATE {table} SET {set_clause}"
    if where_clause:
        query += f" WHERE {where_clause}"

    conn_params = _build_conn_params(merged)
    conn = await asyncpg.connect(**conn_params)
    try:
        result = await conn.execute(query, *all_values)
        rowcount = int(result.split()[-1]) if result else 0
        log.info("postgres.update", table=table, rowcount=rowcount)
        return {"rowcount": rowcount}
    finally:
        await conn.close()


@register_node("postgres.delete")
async def pg_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """DELETE rows from a table matching WHERE conditions.

    config/input_data:
      host, port, user, password, database — connection params
      table — target table name
      where — dict of {column: value} for the WHERE clause (AND-joined)
    """
    merged = {**config, **input_data}
    table = merged.get("table")
    where = merged.get("where", {})
    if not table:
        raise ValueError("table is required for postgres.delete")

    where_columns = list(where.keys())
    where_values = [where[c] for c in where_columns]
    where_clause = " AND ".join(f"{c} = ${i + 1}" for i, c in enumerate(where_columns))

    query = f"DELETE FROM {table}"
    if where_clause:
        query += f" WHERE {where_clause}"

    conn_params = _build_conn_params(merged)
    conn = await asyncpg.connect(**conn_params)
    try:
        result = await conn.execute(query, *where_values)
        rowcount = int(result.split()[-1]) if result else 0
        log.info("postgres.delete", table=table, rowcount=rowcount)
        return {"rowcount": rowcount}
    finally:
        await conn.close()
