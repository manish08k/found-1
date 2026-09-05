"""
CrateDB distributed SQL database integration.

Executes SQL queries against a CrateDB cluster using its HTTP endpoint.

Credential fields:
  - host     : CrateDB host (e.g. localhost or my-cluster.example.com)
  - username : CrateDB username (default: crate)
  - password : CrateDB password (may be empty for default installation)
  - port     : HTTP port (default: 4200)
  - use_ssl  : Whether to use HTTPS (default: False)

HTTP endpoint: http://{host}:{port}/_sql
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> tuple[httpx.AsyncClient, str]:
    """Returns (client, base_url)."""
    creds = await get_credential_data(credential_id, db)
    host = creds.get("host", "localhost").strip()
    username = creds.get("username", "crate")
    password = creds.get("password", "")
    port = int(creds.get("port", 4200))
    use_ssl = bool(creds.get("use_ssl", False))

    if not host:
        raise ValueError("CrateDB credential missing 'host'")

    scheme = "https" if use_ssl else "http"
    base_url = f"{scheme}://{host}:{port}"

    auth = (username, password) if username else None
    client = httpx.AsyncClient(
        base_url=base_url,
        auth=auth,
        headers={"Content-Type": "application/json"},
        timeout=60.0,
    )
    return client, base_url


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"CrateDB HTTP error {r.status_code}: {detail}")


def _parse_result(data: dict) -> dict:
    """Parse CrateDB SQL response into columns/rows."""
    cols = data.get("cols", [])
    rows = data.get("rows", [])
    row_count = data.get("rowcount", len(rows))
    duration = data.get("duration")

    records = [dict(zip(cols, row)) for row in rows]
    return {
        "columns": cols,
        "rows": records,
        "rowcount": row_count,
        "duration_ms": duration,
    }


@register_node("cratedb.execute_query")
async def cratedb_execute_query(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Execute an arbitrary SQL query against CrateDB.

    Config:
      - query  : The SQL query string (required)
      - args   : Optional list of positional parameters for parameterized queries
      - bulk_args : Optional list of lists for bulk operations

    Returns:
      - columns    : List of column names
      - rows       : List of dicts (column -> value)
      - rowcount   : Number of rows affected or returned
      - duration_ms: Query execution time in milliseconds
    """
    query = config.get("query") or input_data.get("query")
    if not query:
        raise ValueError("cratedb.execute_query requires 'query'")

    args = config.get("args") or input_data.get("args")
    bulk_args = config.get("bulk_args") or input_data.get("bulk_args")

    payload: dict = {"stmt": query}
    if args:
        payload["args"] = args
    if bulk_args:
        payload["bulk_args"] = bulk_args

    client, _ = await _client(credential_id, db)
    async with client:
        r = await client.post("/_sql", json=payload)
        _raise_for_status(r)
        data = r.json()

        # CrateDB returns errors inline with status 200 in some versions
        if "error" in data:
            err = data["error"]
            raise ValueError(f"CrateDB query error [{err.get('code')}]: {err.get('message')}")

    return _parse_result(data)


@register_node("cratedb.list_tables")
async def cratedb_list_tables(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List tables in a CrateDB schema.

    Config:
      - schema : Schema name to list tables from (default: 'doc')
    """
    schema = config.get("schema") or input_data.get("schema", "doc")

    query = """
        SELECT table_name, table_schema, number_of_shards, number_of_replicas
        FROM information_schema.tables
        WHERE table_schema = ?
        ORDER BY table_name
    """

    client, _ = await _client(credential_id, db)
    async with client:
        r = await client.post("/_sql", json={"stmt": query.strip(), "args": [schema]})
        _raise_for_status(r)
        data = r.json()

    result = _parse_result(data)
    result["schema"] = schema
    return result


@register_node("cratedb.describe_table")
async def cratedb_describe_table(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Describe the columns and data types of a CrateDB table.

    Config:
      - table  : Table name (required)
      - schema : Schema name (default: 'doc')
    """
    table = config.get("table") or input_data.get("table")
    if not table:
        raise ValueError("cratedb.describe_table requires 'table'")
    schema = config.get("schema") or input_data.get("schema", "doc")

    query = """
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = ? AND table_name = ?
        ORDER BY ordinal_position
    """

    client, _ = await _client(credential_id, db)
    async with client:
        r = await client.post("/_sql", json={"stmt": query.strip(), "args": [schema, table]})
        _raise_for_status(r)
        data = r.json()

    result = _parse_result(data)
    result["table"] = table
    result["schema"] = schema
    return result


@register_node("cratedb.list_schemas")
async def cratedb_list_schemas(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all schemas in the CrateDB cluster."""
    query = """
        SELECT schema_name
        FROM information_schema.schemata
        ORDER BY schema_name
    """

    client, _ = await _client(credential_id, db)
    async with client:
        r = await client.post("/_sql", json={"stmt": query.strip()})
        _raise_for_status(r)
        data = r.json()

    result = _parse_result(data)
    result["schemas"] = [row["schema_name"] for row in result["rows"]]
    return result


@register_node("cratedb.cluster_info")
async def cratedb_cluster_info(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve CrateDB cluster health and node information."""
    query = """
        SELECT id, name, hostname, version['number'] as version,
               heap['max'] as heap_max, heap['used'] as heap_used,
               os['available_processors'] as cpus
        FROM sys.nodes
        ORDER BY name
    """

    client, _ = await _client(credential_id, db)
    async with client:
        r = await client.post("/_sql", json={"stmt": query.strip()})
        _raise_for_status(r)
        data = r.json()

    result = _parse_result(data)
    result["node_count"] = len(result["rows"])
    return result
