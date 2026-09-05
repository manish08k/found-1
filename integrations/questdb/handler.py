"""
QuestDB time-series database integration.

Provides SQL query execution, data ingestion via the import endpoint,
and table listing via the QuestDB HTTP API.

Credential fields:
  - host     : QuestDB host (e.g. 'localhost' or 'my-questdb.example.com').
  - port     : HTTP API port (default 9000).
  - username : QuestDB username (leave empty if auth is disabled).
  - password : QuestDB password (leave empty if auth is disabled).

Endpoints:
  - Query / DDL : http://{host}:{port}/exec
  - Import (CSV) : http://{host}:{port}/imp
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


def _build_base_url(creds: dict) -> str:
    host = creds.get("host", "localhost")
    port = int(creds.get("port", 9000))
    return f"http://{host}:{port}"


def _build_client(creds: dict) -> httpx.AsyncClient:
    base_url = _build_base_url(creds)
    username = creds.get("username")
    password = creds.get("password")
    auth = (username, password) if username and password else None
    return httpx.AsyncClient(base_url=base_url, auth=auth, timeout=60.0)


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"QuestDB API error {r.status_code}: {detail}")


@register_node("questdb.execute_query")
async def questdb_execute_query(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Execute a SQL SELECT (or any read-only) query against QuestDB.

    Params:
      - query (required): SQL statement to execute.
      - limit: Row limit in the form 'offset,count' or just 'count' (e.g. '0,100').
      - count: bool — include total row count in response (default False).
      - nm: bool — if True, include column names in the response metadata (default True).
      - timings: bool — include query timing info (default False).
    """
    creds = await get_credential_data(credential_id, db)

    query = config.get("query") or input_data.get("query")
    if not query:
        raise ValueError("questdb.execute_query requires 'query'")

    params: dict = {"query": query}

    limit = config.get("limit") or input_data.get("limit")
    if limit is not None:
        params["limit"] = str(limit)

    count = config.get("count") or input_data.get("count", False)
    if count:
        params["count"] = "true"

    nm = config.get("nm")
    if nm is None:
        nm = input_data.get("nm", True)
    params["nm"] = "true" if nm else "false"

    timings = config.get("timings") or input_data.get("timings", False)
    if timings:
        params["timings"] = "true"

    async with _build_client(creds) as client:
        r = await client.get("/exec", params=params)
        _raise_for_status(r)
        data = r.json()

    if "error" in data:
        raise ValueError(f"QuestDB query error: {data['error']} (position {data.get('position')})")

    columns = data.get("columns", [])
    dataset = data.get("dataset", [])
    log.info("questdb.execute_query", rows=len(dataset), query_preview=query[:120])
    return {
        "columns": columns,
        "dataset": dataset,
        "count": data.get("count"),
        "timings": data.get("timings"),
        "query": query,
    }


@register_node("questdb.execute_insert")
async def questdb_execute_insert(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Execute a SQL INSERT / CREATE / DROP or other DDL/DML statement.

    Params:
      - query (required): SQL statement to execute (INSERT, CREATE TABLE, DROP, etc.).
    """
    creds = await get_credential_data(credential_id, db)

    query = config.get("query") or input_data.get("query")
    if not query:
        raise ValueError("questdb.execute_insert requires 'query'")

    params: dict = {"query": query}

    async with _build_client(creds) as client:
        r = await client.get("/exec", params=params)
        _raise_for_status(r)
        data = r.json()

    if "error" in data:
        raise ValueError(f"QuestDB error: {data['error']} (position {data.get('position')})")

    log.info("questdb.execute_insert", ddl=data.get("ddl"), query_preview=query[:120])
    return {
        "ddl": data.get("ddl"),
        "count": data.get("count"),
        "query": query,
        "response": data,
    }


@register_node("questdb.list_tables")
async def questdb_list_tables(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    List all tables in the QuestDB instance.

    No additional params required beyond credentials.
    """
    creds = await get_credential_data(credential_id, db)

    async with _build_client(creds) as client:
        r = await client.get("/exec", params={"query": "SHOW TABLES"})
        _raise_for_status(r)
        data = r.json()

    if "error" in data:
        raise ValueError(f"QuestDB error: {data['error']}")

    dataset = data.get("dataset", [])
    # SHOW TABLES returns [[table_name], ...] rows
    tables = [row[0] if isinstance(row, list) else row for row in dataset]
    log.info("questdb.list_tables", count=len(tables))
    return {"tables": tables, "columns": data.get("columns", []), "raw": dataset}
