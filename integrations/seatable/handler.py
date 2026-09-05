"""SeaTable integration — collaborative spreadsheet management.

Credential fields:
  - server_url : SeaTable server URL (e.g. https://cloud.seatable.io)
  - api_token  : SeaTable API token
  - base_name  : Name of the base (database)

Auth: JWT access token obtained from app-access-token endpoint.
Token URL: {server_url}/api/v2.1/dtable/app-access-token/

Nodes:
  - seatable.list_tables : list all tables in the base
  - seatable.list_rows   : list rows in a specific table
  - seatable.create_row  : add a new row to a table
  - seatable.update_row  : update an existing row
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

async def _get_access_token(creds: dict) -> str:
    """Exchange the API token for a short-lived JWT access token."""
    server_url = creds.get("server_url", "").rstrip("/")
    api_token = creds.get("api_token")
    if not server_url:
        raise ValueError("SeaTable credential is missing 'server_url'")
    if not api_token:
        raise ValueError("SeaTable credential is missing 'api_token'")

    token_url = f"{server_url}/api/v2.1/dtable/app-access-token/"
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(token_url, headers={"Authorization": f"Token {api_token}"})
        r.raise_for_status()
        data = r.json()
    access_token = data.get("access_token")
    if not access_token:
        raise ValueError(f"Failed to obtain SeaTable access token: {data}")
    return access_token


async def _client(credential_id: str, db) -> tuple[httpx.AsyncClient, str, str]:
    """Return (AsyncClient, dtable_uuid, server_url)."""
    creds = await get_credential_data(credential_id, db)
    server_url = creds.get("server_url", "").rstrip("/")
    base_name = creds.get("base_name", "")

    access_token = await _get_access_token(creds)

    client = httpx.AsyncClient(
        base_url=f"{server_url}/api/v2.1/dtable/",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )
    return client, base_name, server_url


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@register_node("seatable.list_tables")
async def list_tables(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all tables in the SeaTable base."""
    log.info("seatable.list_tables")
    creds = await get_credential_data(credential_id, db)
    server_url = creds.get("server_url", "").rstrip("/")
    access_token = await _get_access_token(creds)

    async with httpx.AsyncClient(
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30.0,
    ) as client:
        r = await client.get(f"{server_url}/api/v2.1/dtable/app-access-token/")
        # Retrieve metadata containing tables
        r2 = await client.get(
            f"{server_url}/dtable-server/api/v1/dtables/",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if r2.is_success:
            data = r2.json()
        else:
            # Try alternate endpoint
            r3 = await client.get(
                f"{server_url}/api/v2.1/workspace/",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            data = r3.json() if r3.is_success else {}

    tables = data.get("tables", data.get("dtables", []))
    log.info("seatable.list_tables.done", count=len(tables))
    return {"tables": tables, "count": len(tables)}


@register_node("seatable.list_rows")
async def list_rows(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List rows in a SeaTable table."""
    table_name = config.get("table_name") or input_data.get("table_name")
    if not table_name:
        raise ValueError("'table_name' is required")

    limit = int(config.get("limit", input_data.get("limit", 100)))
    start = int(config.get("start", input_data.get("start", 0)))

    log.info("seatable.list_rows", table=table_name, limit=limit)
    creds = await get_credential_data(credential_id, db)
    server_url = creds.get("server_url", "").rstrip("/")
    access_token = await _get_access_token(creds)

    params = {"table_name": table_name, "limit": limit, "start": start}
    async with httpx.AsyncClient(
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30.0,
    ) as client:
        r = await client.get(f"{server_url}/dtable-server/api/v1/dtables/rows/", params=params)
        r.raise_for_status()
        data = r.json()

    rows = data.get("rows", [])
    log.info("seatable.list_rows.done", table=table_name, count=len(rows))
    return {"rows": rows, "count": len(rows), "table_name": table_name}


@register_node("seatable.create_row")
async def create_row(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Append a new row to a SeaTable table."""
    table_name = config.get("table_name") or input_data.get("table_name")
    if not table_name:
        raise ValueError("'table_name' is required")
    row = config.get("row") or input_data.get("row", {})

    log.info("seatable.create_row", table=table_name)
    creds = await get_credential_data(credential_id, db)
    server_url = creds.get("server_url", "").rstrip("/")
    access_token = await _get_access_token(creds)

    payload = {"table_name": table_name, "row": row}
    async with httpx.AsyncClient(
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        timeout=30.0,
    ) as client:
        r = await client.post(f"{server_url}/dtable-server/api/v1/dtables/rows/", json=payload)
        r.raise_for_status()
        data = r.json()

    log.info("seatable.create_row.done", table=table_name)
    return {"row": data, "table_name": table_name}


@register_node("seatable.update_row")
async def update_row(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Update an existing row in a SeaTable table."""
    table_name = config.get("table_name") or input_data.get("table_name")
    row_id = config.get("row_id") or input_data.get("row_id")
    if not table_name:
        raise ValueError("'table_name' is required")
    if not row_id:
        raise ValueError("'row_id' is required")
    row = config.get("row") or input_data.get("row", {})

    log.info("seatable.update_row", table=table_name, row_id=row_id)
    creds = await get_credential_data(credential_id, db)
    server_url = creds.get("server_url", "").rstrip("/")
    access_token = await _get_access_token(creds)

    payload = {"table_name": table_name, "row_id": row_id, "row": row}
    async with httpx.AsyncClient(
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        timeout=30.0,
    ) as client:
        r = await client.put(f"{server_url}/dtable-server/api/v1/dtables/rows/", json=payload)
        r.raise_for_status()
        data = r.json()

    log.info("seatable.update_row.done", table=table_name, row_id=row_id)
    return {"row": data, "row_id": row_id, "table_name": table_name, "updated": True}
