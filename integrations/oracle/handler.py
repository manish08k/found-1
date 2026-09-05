"""
Oracle Database integration.

Auth: username + password + dsn (Data Source Name / connect string).

Credential fields:
  - username (str) : Oracle DB username.
  - password (str) : Oracle DB password.
  - dsn (str)      : Connect descriptor, e.g. "host:1521/service" or TNS alias.

Nodes:
  - oracle.execute_query     : Run a SELECT and return rows.
  - oracle.execute_statement : Run DML/DDL (INSERT, UPDATE, DELETE, CREATE …).
  - oracle.list_tables       : List accessible tables in a schema.

Uses the `oracledb` library (python-oracledb). Async execution via run_in_executor.
"""
import asyncio
import structlog
import httpx  # noqa: F401 — imported for platform consistency

from core.execution_engine import register_node
from oauth.flow import get_credential_data

try:
    import oracledb
    _ORACLE_AVAILABLE = True
except ImportError:
    oracledb = None  # type: ignore[assignment]
    _ORACLE_AVAILABLE = False

log = structlog.get_logger(__name__)


async def _get_creds(credential_id: str, db) -> tuple[str, str, str]:
    creds = await get_credential_data(credential_id, db)
    username = creds.get("username")
    password = creds.get("password")
    dsn = creds.get("dsn")
    if not username:
        raise ValueError("Oracle credential missing 'username'")
    if not password:
        raise ValueError("Oracle credential missing 'password'")
    if not dsn:
        raise ValueError("Oracle credential missing 'dsn'")
    return username, password, dsn


def _check_oracledb() -> None:
    if not _ORACLE_AVAILABLE:
        raise ImportError(
            "The 'oracledb' package is required for Oracle integration. "
            "Install it with: pip install oracledb"
        )


def _sync_execute_query(username: str, password: str, dsn: str, sql: str, bind_vars: dict | list) -> dict:
    """Blocking helper — runs in executor thread pool."""
    with oracledb.connect(user=username, password=password, dsn=dsn) as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, bind_vars)
            columns = [col[0].lower() for col in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            records = [dict(zip(columns, row)) for row in rows]
    return {"columns": columns, "rows": records, "row_count": len(records)}


def _sync_execute_statement(username: str, password: str, dsn: str, sql: str, bind_vars: dict | list, commit: bool) -> dict:
    """Blocking helper — runs in executor thread pool."""
    with oracledb.connect(user=username, password=password, dsn=dsn) as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, bind_vars)
            rowcount = cursor.rowcount
        if commit:
            conn.commit()
    return {"rows_affected": rowcount, "committed": commit}


def _sync_list_tables(username: str, password: str, dsn: str, schema: str | None) -> dict:
    """Blocking helper — runs in executor thread pool."""
    with oracledb.connect(user=username, password=password, dsn=dsn) as conn:
        with conn.cursor() as cursor:
            if schema:
                cursor.execute(
                    "SELECT TABLE_NAME, OWNER FROM ALL_TABLES WHERE OWNER = :owner ORDER BY TABLE_NAME",
                    {"owner": schema.upper()},
                )
            else:
                cursor.execute(
                    "SELECT TABLE_NAME, OWNER FROM USER_TABLES ORDER BY TABLE_NAME"
                )
            rows = cursor.fetchall()
            tables = [{"table_name": r[0], "owner": r[1] if len(r) > 1 else None} for r in rows]
    return {"tables": tables, "count": len(tables)}


@register_node("oracle.execute_query")
async def execute_query(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Execute a SELECT query and return rows as a list of dicts.

    Config / input keys:
      - sql (str, required)   : SQL SELECT statement. Use :name placeholders.
      - bind_vars (dict|list) : Bind variables. Default {}.
    """
    _check_oracledb()
    username, password, dsn = await _get_creds(credential_id, db)

    sql = config.get("sql") or input_data.get("sql")
    if not sql:
        raise ValueError("oracle.execute_query requires 'sql'")
    bind_vars = config.get("bind_vars") or input_data.get("bind_vars") or {}

    log.info("oracle.execute_query", dsn=dsn, sql_preview=sql[:80])
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, _sync_execute_query, username, password, dsn, sql, bind_vars
    )
    return result


@register_node("oracle.execute_statement")
async def execute_statement(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Execute a DML or DDL statement (INSERT, UPDATE, DELETE, CREATE, etc.).

    Config / input keys:
      - sql (str, required)   : SQL statement. Use :name placeholders.
      - bind_vars (dict|list) : Bind variables. Default {}.
      - commit (bool)         : Auto-commit after execution. Default True.
    """
    _check_oracledb()
    username, password, dsn = await _get_creds(credential_id, db)

    sql = config.get("sql") or input_data.get("sql")
    if not sql:
        raise ValueError("oracle.execute_statement requires 'sql'")
    bind_vars = config.get("bind_vars") or input_data.get("bind_vars") or {}
    commit = str(config.get("commit") or input_data.get("commit", True)).lower() != "false"

    log.info("oracle.execute_statement", dsn=dsn, sql_preview=sql[:80], commit=commit)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, _sync_execute_statement, username, password, dsn, sql, bind_vars, commit
    )
    return result


@register_node("oracle.list_tables")
async def list_tables(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List tables visible to the connected user.

    Config / input keys:
      - schema (str) : Owner/schema name. If omitted, lists tables owned by current user.
    """
    _check_oracledb()
    username, password, dsn = await _get_creds(credential_id, db)

    schema = config.get("schema") or input_data.get("schema") or None

    log.info("oracle.list_tables", dsn=dsn, schema=schema)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, _sync_list_tables, username, password, dsn, schema
    )
    return result
