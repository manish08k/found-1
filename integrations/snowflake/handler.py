"""
Snowflake SQL REST API v2 integration.

Credential fields:
  - account: e.g. xy12345.us-east-1
  - username: Snowflake username
  - password: Snowflake password
  - warehouse: default warehouse
  - database: default database
  - schema: default schema (e.g. PUBLIC)

Auth: HTTP Basic (username:password)
Base URL: https://{account}.snowflakecomputing.com/api/v2
"""
import base64
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> tuple[httpx.AsyncClient, dict]:
    creds = await get_credential_data(credential_id, db)
    account = creds.get("account")
    username = creds.get("username")
    password = creds.get("password")
    warehouse = creds.get("warehouse", "COMPUTE_WH")
    database = creds.get("database", "")
    schema = creds.get("schema", "PUBLIC")
    if not account:
        raise ValueError("Snowflake credential is missing 'account'")
    if not username:
        raise ValueError("Snowflake credential is missing 'username'")
    if not password:
        raise ValueError("Snowflake credential is missing 'password'")
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    base_url = f"https://{account}.snowflakecomputing.com/api/v2"
    client = httpx.AsyncClient(
        base_url=base_url,
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Snowflake-Authorization-Token-Type": "BASIC",
        },
        timeout=60.0,
    )
    defaults = {"warehouse": warehouse, "database": database, "schema": schema}
    return client, defaults


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Snowflake API error {r.status_code}: {detail}")
    try:
        return r.json()
    except Exception:
        return {"raw": r.text}


async def _execute_sql(client: httpx.AsyncClient, sql: str, defaults: dict,
                        config: dict, input_data: dict) -> dict:
    body = {
        "statement": sql,
        "warehouse": config.get("warehouse") or input_data.get("warehouse") or defaults["warehouse"],
        "database": config.get("database") or input_data.get("database") or defaults["database"],
        "schema": config.get("schema") or input_data.get("schema") or defaults["schema"],
    }
    timeout = config.get("timeout") or input_data.get("timeout")
    if timeout:
        body["timeout"] = int(timeout)
    r = await client.post("/statements", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@register_node("snowflake.execute_query")
async def snowflake_execute_query(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /api/v2/statements — execute a SQL query and return results."""
    sql = config.get("query") or input_data.get("query")
    if not sql:
        raise ValueError("snowflake.execute_query requires 'query'")
    client, defaults = await _client(credential_id, db)
    async with client as c:
        return await _execute_sql(c, sql, defaults, config, input_data)


@register_node("snowflake.execute_statement")
async def snowflake_execute_statement(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /api/v2/statements — execute a SQL statement (DML/DDL)."""
    sql = config.get("statement") or input_data.get("statement")
    if not sql:
        raise ValueError("snowflake.execute_statement requires 'statement'")
    client, defaults = await _client(credential_id, db)
    async with client as c:
        return await _execute_sql(c, sql, defaults, config, input_data)


@register_node("snowflake.list_databases")
async def snowflake_list_databases(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Execute SHOW DATABASES — list all accessible databases."""
    client, defaults = await _client(credential_id, db)
    async with client as c:
        return await _execute_sql(c, "SHOW DATABASES", defaults, config, input_data)


@register_node("snowflake.list_schemas")
async def snowflake_list_schemas(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Execute SHOW SCHEMAS — list schemas in a database."""
    database = config.get("database") or input_data.get("database")
    sql = f"SHOW SCHEMAS IN DATABASE {database}" if database else "SHOW SCHEMAS"
    client, defaults = await _client(credential_id, db)
    async with client as c:
        return await _execute_sql(c, sql, defaults, config, input_data)


@register_node("snowflake.list_tables")
async def snowflake_list_tables(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Execute SHOW TABLES — list tables in a schema."""
    database = config.get("database") or input_data.get("database")
    schema = config.get("schema") or input_data.get("schema")
    if database and schema:
        sql = f"SHOW TABLES IN {database}.{schema}"
    elif database:
        sql = f"SHOW TABLES IN DATABASE {database}"
    else:
        sql = "SHOW TABLES"
    client, defaults = await _client(credential_id, db)
    async with client as c:
        return await _execute_sql(c, sql, defaults, config, input_data)


@register_node("snowflake.describe_table")
async def snowflake_describe_table(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Execute DESCRIBE TABLE — describe a table's columns."""
    table = config.get("table") or input_data.get("table")
    if not table:
        raise ValueError("snowflake.describe_table requires 'table'")
    sql = f"DESCRIBE TABLE {table}"
    client, defaults = await _client(credential_id, db)
    async with client as c:
        return await _execute_sql(c, sql, defaults, config, input_data)


@register_node("snowflake.insert_data")
async def snowflake_insert_data(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Execute INSERT INTO — insert rows into a table."""
    table = config.get("table") or input_data.get("table")
    columns = config.get("columns") or input_data.get("columns")
    values = config.get("values") or input_data.get("values")
    if not table or not values:
        raise ValueError("snowflake.insert_data requires 'table' and 'values'")
    if columns:
        cols_str = ", ".join(columns)
        vals_str = ", ".join(
            "(" + ", ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in row) + ")"
            for row in values
        )
        sql = f"INSERT INTO {table} ({cols_str}) VALUES {vals_str}"
    else:
        vals_str = ", ".join(
            "(" + ", ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in row) + ")"
            for row in values
        )
        sql = f"INSERT INTO {table} VALUES {vals_str}"
    client, defaults = await _client(credential_id, db)
    async with client as c:
        return await _execute_sql(c, sql, defaults, config, input_data)


@register_node("snowflake.create_table")
async def snowflake_create_table(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Execute CREATE TABLE — create a new table."""
    table = config.get("table") or input_data.get("table")
    columns_def = config.get("columns_def") or input_data.get("columns_def")
    if not table or not columns_def:
        raise ValueError("snowflake.create_table requires 'table' and 'columns_def'")
    if_not_exists = config.get("if_not_exists", False) or input_data.get("if_not_exists", False)
    clause = "IF NOT EXISTS " if if_not_exists else ""
    sql = f"CREATE TABLE {clause}{table} ({columns_def})"
    client, defaults = await _client(credential_id, db)
    async with client as c:
        return await _execute_sql(c, sql, defaults, config, input_data)


@register_node("snowflake.load_data")
async def snowflake_load_data(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Execute COPY INTO from a stage — load data from a stage into a table."""
    table = config.get("table") or input_data.get("table")
    stage = config.get("stage") or input_data.get("stage")
    if not table or not stage:
        raise ValueError("snowflake.load_data requires 'table' and 'stage'")
    file_format = config.get("file_format") or input_data.get("file_format", "CSV")
    sql = f"COPY INTO {table} FROM {stage} FILE_FORMAT = (TYPE = '{file_format}')"
    client, defaults = await _client(credential_id, db)
    async with client as c:
        return await _execute_sql(c, sql, defaults, config, input_data)


async def test_connection(credential_id: str, db) -> dict:
    """Test Snowflake connection by running SELECT CURRENT_VERSION()."""
    client, defaults = await _client(credential_id, db)
    async with client as c:
        result = await _execute_sql(c, "SELECT CURRENT_VERSION()", defaults, {}, {})
    return {"ok": True, "result": result}
