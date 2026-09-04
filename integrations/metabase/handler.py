"""
Metabase integration.

Credential fields:
  - base_url: Metabase instance URL (e.g. https://your-metabase.example.com)
  - username: Metabase username/email
  - password: Metabase password

Auth: POST /api/session to get session token, then X-Metabase-Session header
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _get_session(base_url: str, username: str, password: str) -> str:
    """Authenticate and return the session token."""
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        r = await client.post(
            "/api/session",
            json={"username": username, "password": password},
        )
        if not r.is_success:
            try:
                detail = r.json()
            except Exception:
                detail = r.text
            raise ValueError(f"Metabase auth error {r.status_code}: {detail}")
        return r.json()["id"]


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    base_url = creds.get("base_url")
    username = creds.get("username")
    password = creds.get("password")
    if not base_url:
        raise ValueError("Metabase credential is missing 'base_url'")
    if not username:
        raise ValueError("Metabase credential is missing 'username'")
    if not password:
        raise ValueError("Metabase credential is missing 'password'")
    session_token = await _get_session(base_url.rstrip("/"), username, password)
    return httpx.AsyncClient(
        base_url=f"{base_url.rstrip('/')}/api",
        headers={
            "X-Metabase-Session": session_token,
            "Content-Type": "application/json",
        },
        timeout=60.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Metabase API error {r.status_code}: {detail}")
    try:
        return r.json()
    except Exception:
        return {"raw": r.text}


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@register_node("metabase.list_databases")
async def metabase_list_databases(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /api/database — list all databases."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/database")
    return _check(r)


@register_node("metabase.list_collections")
async def metabase_list_collections(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /api/collection — list all collections."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/collection")
    return _check(r)


@register_node("metabase.list_questions")
async def metabase_list_questions(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /api/card — list all questions/cards."""
    params: dict = {}
    collection_id = config.get("collection_id") or input_data.get("collection_id")
    if collection_id:
        params["collection_id"] = collection_id
    async with await _client(credential_id, db) as client:
        r = await client.get("/card", params=params)
    return _check(r)


@register_node("metabase.get_question")
async def metabase_get_question(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /api/card/{id} — get a specific question/card."""
    card_id = config.get("card_id") or input_data.get("card_id")
    if not card_id:
        raise ValueError("metabase.get_question requires 'card_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/card/{card_id}")
    return _check(r)


@register_node("metabase.run_question")
async def metabase_run_question(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /api/card/{id}/query — run a question and get results."""
    card_id = config.get("card_id") or input_data.get("card_id")
    if not card_id:
        raise ValueError("metabase.run_question requires 'card_id'")
    parameters = config.get("parameters") or input_data.get("parameters") or []
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/card/{card_id}/query", json={"parameters": parameters})
    return _check(r)


@register_node("metabase.list_dashboards")
async def metabase_list_dashboards(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /api/dashboard — list all dashboards."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/dashboard")
    return _check(r)


@register_node("metabase.get_dashboard")
async def metabase_get_dashboard(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /api/dashboard/{id} — get a specific dashboard."""
    dashboard_id = config.get("dashboard_id") or input_data.get("dashboard_id")
    if not dashboard_id:
        raise ValueError("metabase.get_dashboard requires 'dashboard_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/dashboard/{dashboard_id}")
    return _check(r)


@register_node("metabase.list_cards")
async def metabase_list_cards(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /api/card — list all cards (alias for list_questions)."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/card")
    return _check(r)


@register_node("metabase.execute_sql")
async def metabase_execute_sql(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /api/dataset — execute an ad-hoc SQL query against a database."""
    database_id = config.get("database_id") or input_data.get("database_id")
    sql = config.get("sql") or input_data.get("sql")
    if not database_id:
        raise ValueError("metabase.execute_sql requires 'database_id'")
    if not sql:
        raise ValueError("metabase.execute_sql requires 'sql'")
    body = {
        "database": int(database_id),
        "type": "native",
        "native": {"query": sql},
    }
    async with await _client(credential_id, db) as client:
        r = await client.post("/dataset", json=body)
    return _check(r)


@register_node("metabase.create_question")
async def metabase_create_question(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /api/card — create a new question/card."""
    name = config.get("name") or input_data.get("name")
    database_id = config.get("database_id") or input_data.get("database_id")
    sql = config.get("sql") or input_data.get("sql")
    if not name or not database_id:
        raise ValueError("metabase.create_question requires 'name' and 'database_id'")
    body: dict = {
        "name": name,
        "dataset_query": {
            "database": int(database_id),
            "type": "native",
            "native": {"query": sql or "SELECT 1"},
        },
        "display": config.get("display") or input_data.get("display") or "table",
        "visualization_settings": config.get("visualization_settings") or input_data.get("visualization_settings") or {},
    }
    collection_id = config.get("collection_id") or input_data.get("collection_id")
    if collection_id:
        body["collection_id"] = collection_id
    async with await _client(credential_id, db) as client:
        r = await client.post("/card", json=body)
    return _check(r)


async def test_connection(credential_id: str, db) -> dict:
    """Test Metabase connection by fetching the current user."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/user/current")
    _check(r)
    return {"ok": True}
