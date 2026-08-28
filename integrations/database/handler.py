"""
Database integration — lets a workflow connect to ANY SQL database
(Postgres, MySQL, SQLite) the *user* owns, using a credential they add
themselves (host/port/user/password), separate from AutoFlow's own
application database.

Design notes:
  - The connection details are stored exactly like any other credential:
    encrypted at rest with credentials/encryption.py, decrypted only in
    worker memory for the duration of one node execution
    (oauth/flow.get_credential_data — the non-OAuth counterpart of
    get_access_token).
  - Two nodes, on purpose:
      database.query    -> read-only (SELECT/WITH/SHOW/EXPLAIN only)
      database.execute   -> write (INSERT/UPDATE/DELETE/DDL)
    Splitting them means a workflow author can't accidentally mutate
    data from a node they only meant to read from, and it lets us apply
    a stricter row cap + always-rollback-on-error policy to the read path.
  - Queries are only ever run as parameterized statements
    (SQLAlchemy `text(...).bindparams(...)`) — config/input values are
    NEVER interpolated into the SQL string. This is the same rule the
    platform enforces for outbound HTTP via ssrf_guard: user-supplied
    data is data, never code.
  - Every call is wrapped in a wall-clock timeout and a row cap so one
    workflow can't hold a worker (or the target DB) hostage.
  - Engines are cached per unique connection signature for the lifetime
    of the worker process, so a workflow that fires often isn't paying
    a fresh TCP+auth handshake on every run.
"""
import asyncio
import re

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

DEFAULT_QUERY_TIMEOUT_SECONDS = 20
MAX_QUERY_TIMEOUT_SECONDS = 60
DEFAULT_MAX_ROWS = 1000
HARD_MAX_ROWS = 10_000

# db_type (chosen by the user when they add the credential) -> SQLAlchemy async driver
_DRIVERS = {
    "postgres": "postgresql+asyncpg",
    "mysql": "mysql+aiomysql",
    "sqlite": "sqlite+aiosqlite",
}

_READ_ONLY_PREFIX = re.compile(r"^\s*(WITH|SELECT|SHOW|EXPLAIN|DESCRIBE|DESC)\b", re.IGNORECASE)

# One cached engine per unique connection signature, reused for the life of
# this worker process. Small deployments will only ever have a handful of
# distinct signatures, so this never grows unbounded in practice.
_ENGINE_CACHE: dict[str, AsyncEngine] = {}


def _build_url(creds: dict) -> str:
    db_type = creds.get("db_type")
    driver = _DRIVERS.get(db_type)
    if not driver:
        raise ValueError(
            f"Unsupported database type '{db_type}'. Supported: {', '.join(_DRIVERS)}"
        )

    if db_type == "sqlite":
        # Path lives in `database`; no host/user/password.
        return f"{driver}:///{creds.get('database', '')}"

    user = creds.get("username", "")
    password = creds.get("password", "")
    host = creds.get("host", "localhost")
    port = creds.get("port") or (5432 if db_type == "postgres" else 3306)
    database = creds.get("database", "")
    from urllib.parse import quote_plus
    auth = f"{quote_plus(user)}:{quote_plus(password)}@" if user else ""
    return f"{driver}://{auth}{host}:{port}/{database}"


def _get_engine(creds: dict) -> AsyncEngine:
    url = _build_url(creds)
    engine = _ENGINE_CACHE.get(url)
    if engine is None:
        connect_args = {}
        if creds.get("db_type") == "postgres":
            connect_args["ssl"] = True if creds.get("ssl") else None
        # pool_pre_ping issues a lightweight "is this connection still
        # alive" check on every checkout — safe and recommended for
        # postgres/sqlite here, but aiomysql 0.2.0's connection.ping()
        # signature isn't compatible with the way SQLAlchemy 2.0.x's
        # dialect calls it (confirmed by running this against a live
        # MySQL instance — every checkout raised a TypeError). Disable
        # it for mysql specifically rather than losing pre-ping safety
        # for every backend; revisit if a future aiomysql/SQLAlchemy
        # release fixes the signature mismatch.
        pre_ping = creds.get("db_type") != "mysql"
        engine = create_async_engine(
            url,
            pool_size=5,
            max_overflow=5,
            pool_pre_ping=pre_ping,
            pool_recycle=1800,
            connect_args={k: v for k, v in connect_args.items() if v is not None},
        )
        _ENGINE_CACHE[url] = engine
    return engine


def _bind_params(config: dict, input_data: dict) -> dict:
    params = config.get("params") or input_data.get("params") or {}
    if not isinstance(params, dict):
        raise ValueError("'params' must be a JSON object of named bind parameters")
    return params


async def _run(engine: AsyncEngine, sql: str, params: dict, timeout: float, fetch: bool, max_rows: int):
    async def _inner():
        async with engine.connect() as conn:
            result = await conn.execute(text(sql), params)
            if fetch:
                rows = result.mappings().fetchmany(max_rows)
                return {
                    "rows": [dict(r) for r in rows],
                    "row_count": len(rows),
                    "truncated": len(rows) == max_rows,
                }
            else:
                await conn.commit()
                return {"row_count": result.rowcount if result.rowcount is not None else 0}

    return await asyncio.wait_for(_inner(), timeout=timeout)


@register_node("database.query")
async def database_query(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Run a read-only SQL query and return rows. Requires a database credential."""
    if not credential_id:
        raise ValueError("database.query requires a database credential")

    sql = (config.get("query") or input_data.get("query") or "").strip()
    if not sql:
        raise ValueError("database.query: 'query' is required")
    if not _READ_ONLY_PREFIX.match(sql):
        raise ValueError(
            "database.query only allows SELECT/WITH/SHOW/EXPLAIN statements. "
            "Use the 'Database Execute' node for INSERT/UPDATE/DELETE/DDL."
        )

    params = _bind_params(config, input_data)
    timeout = min(float(config.get("timeout", DEFAULT_QUERY_TIMEOUT_SECONDS)), MAX_QUERY_TIMEOUT_SECONDS)
    max_rows = min(int(config.get("max_rows", DEFAULT_MAX_ROWS)), HARD_MAX_ROWS)

    creds = await get_credential_data(credential_id, db)
    engine = _get_engine(creds)

    log.info("database_query", db_type=creds.get("db_type"), max_rows=max_rows)
    try:
        return await _run(engine, sql, params, timeout, fetch=True, max_rows=max_rows)
    except asyncio.TimeoutError:
        raise ValueError(f"database.query timed out after {timeout}s")


@register_node("database.execute")
async def database_execute(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Run a write statement (INSERT/UPDATE/DELETE/DDL). Requires a database credential."""
    if not credential_id:
        raise ValueError("database.execute requires a database credential")

    sql = (config.get("query") or input_data.get("query") or "").strip()
    if not sql:
        raise ValueError("database.execute: 'query' is required")

    params = _bind_params(config, input_data)
    timeout = min(float(config.get("timeout", DEFAULT_QUERY_TIMEOUT_SECONDS)), MAX_QUERY_TIMEOUT_SECONDS)

    creds = await get_credential_data(credential_id, db)
    engine = _get_engine(creds)

    log.info("database_execute", db_type=creds.get("db_type"))
    try:
        return await _run(engine, sql, params, timeout, fetch=False, max_rows=0)
    except asyncio.TimeoutError:
        raise ValueError(f"database.execute timed out after {timeout}s")


async def test_connection(creds: dict) -> None:
    """Used by the /credentials/{id}/test endpoint for db-type credentials."""
    engine = _get_engine(creds)
    async with engine.connect() as conn:
        await asyncio.wait_for(conn.execute(text("SELECT 1")), timeout=5)
