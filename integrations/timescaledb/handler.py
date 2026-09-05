"""
TimescaleDB time-series PostgreSQL integration.

Provides SQL querying, data insertion, and hypertable listing via asyncpg.

Credential fields:
  - host     : Database host
  - port     : Database port (default 5432)
  - database : Database name
  - username : Database username
  - password : Database password
"""
import structlog
import httpx  # noqa: F401 — kept for consistency with platform pattern

from core.execution_engine import register_node
from oauth.flow import get_credential_data

try:
    import asyncpg
    _ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None  # type: ignore[assignment]
    _ASYNCPG_AVAILABLE = False

log = structlog.get_logger(__name__)


async def _get_dsn(credential_id: str, db) -> str:
    creds = await get_credential_data(credential_id, db)
    host = creds.get("host", "localhost")
    port = int(creds.get("port", 5432))
    database = creds.get("database")
    username = creds.get("username")
    password = creds.get("password", "")

    if not database:
        raise ValueError("TimescaleDB credential missing 'database'")
    if not username:
        raise ValueError("TimescaleDB credential missing 'username'")

    return f"postgresql://{username}:{password}@{host}:{port}/{database}"


def _require_asyncpg() -> None:
    if not _ASYNCPG_AVAILABLE:
        raise ImportError(
            "asyncpg is required for TimescaleDB integration. "
            "Install it with: pip install asyncpg"
        )


@register_node("timescaledb.query")
async def tsdb_query(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Execute a SQL query against TimescaleDB."""
    _require_asyncpg()

    sql = config.get("sql") or input_data.get("sql")
    params = config.get("params") or input_data.get("params", [])
    if not sql:
        raise ValueError("timescaledb.query requires 'sql'")

    dsn = await _get_dsn(credential_id, db)
    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(sql, *params)
        result = [dict(row) for row in rows]
    finally:
        await conn.close()

    log.info("timescaledb.query", row_count=len(result))
    return {"rows": result, "row_count": len(result)}


@register_node("timescaledb.insert")
async def tsdb_insert(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Insert a row into a TimescaleDB table."""
    _require_asyncpg()

    table = config.get("table") or input_data.get("table")
    data_row = config.get("data") or input_data.get("data")
    if not table:
        raise ValueError("timescaledb.insert requires 'table'")
    if not data_row or not isinstance(data_row, dict):
        raise ValueError("timescaledb.insert requires 'data' as a dict of column->value")

    columns = list(data_row.keys())
    values = list(data_row.values())
    placeholders = ", ".join(f"${i + 1}" for i in range(len(columns)))
    col_list = ", ".join(f'"{c}"' for c in columns)
    sql = f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders}) RETURNING *'

    dsn = await _get_dsn(credential_id, db)
    conn = await asyncpg.connect(dsn)
    try:
        row = await conn.fetchrow(sql, *values)
        inserted = dict(row) if row else {}
    finally:
        await conn.close()

    log.info("timescaledb.insert", table=table, inserted=bool(inserted))
    return {"inserted": inserted, "table": table}


@register_node("timescaledb.list_hypertables")
async def tsdb_list_hypertables(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all TimescaleDB hypertables in the current database."""
    _require_asyncpg()

    sql = (
        "SELECT hypertable_schema, hypertable_name, num_dimensions, "
        "num_chunks, compression_enabled "
        "FROM timescaledb_information.hypertables "
        "ORDER BY hypertable_schema, hypertable_name"
    )

    dsn = await _get_dsn(credential_id, db)
    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(sql)
        hypertables = [dict(row) for row in rows]
    finally:
        await conn.close()

    log.info("timescaledb.list_hypertables", count=len(hypertables))
    return {"hypertables": hypertables, "count": len(hypertables)}
