"""
FileMaker Data API integration.

Provides CRUD operations and find queries against a FileMaker Server
hosted database using the FileMaker Data API v1.

Credential fields:
  - host     : FileMaker Server host URL, e.g. https://filemaker.example.com
  - database : Target database name
  - username : FileMaker account username
  - password : FileMaker account password

Auth: POST to /fmi/data/v1/databases/{database}/sessions to obtain a
session token, then pass as Authorization: Bearer <token>.
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _get_session_token(host: str, database: str, username: str, password: str) -> str:
    """Authenticate to FileMaker Data API and return a session token."""
    url = f"{host}/fmi/data/v1/databases/{database}/sessions"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            url,
            auth=(username, password),
            headers={"Content-Type": "application/json"},
            json={},
        )
        if r.status_code >= 400:
            try:
                detail = r.json()
            except Exception:
                detail = r.text
            raise RuntimeError(
                f"FileMaker authentication failed {r.status_code}: {detail}"
            )
        data = r.json()
        token = (
            data.get("response", {}).get("token")
            or data.get("token")
        )
        if not token:
            raise RuntimeError("FileMaker did not return a session token")
        return token


async def _client(credential_id: str, db):
    """Return (httpx.AsyncClient, host, database) after authenticating."""
    creds = await get_credential_data(credential_id, db)
    host = creds.get("host", "").rstrip("/")
    database = creds.get("database")
    username = creds.get("username")
    password = creds.get("password")

    for field in ("host", "database", "username", "password"):
        if not creds.get(field):
            raise ValueError(f"FileMaker credential missing '{field}'")

    token = await _get_session_token(host, database, username, password)
    client = httpx.AsyncClient(
        base_url=f"{host}/fmi/data/v1/databases/{database}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )
    return client, host, database


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 400:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise RuntimeError(f"FileMaker API error {r.status_code}: {detail}")


@register_node("filemaker.get_records")
async def get_records(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve records from a FileMaker layout."""
    layout = config.get("layout") or input_data.get("layout")
    if not layout:
        raise ValueError("'layout' is required in config or input_data")

    limit = int(config.get("limit", 100))
    offset = int(config.get("offset", 1))
    sort_field = config.get("sort_field")
    sort_order = config.get("sort_order", "ascend")

    params: dict = {"_limit": limit, "_offset": offset}
    if sort_field:
        params["_sort"] = f'[{{"fieldName":"{sort_field}","sortOrder":"{sort_order}"}}]'

    log.info("filemaker.get_records", layout=layout, limit=limit)

    async with (await _client(credential_id, db))[0] as client:
        r = await client.get(f"/layouts/{layout}/records", params=params)
        _raise_for_status(r)
        data = r.json()

    records = data.get("response", {}).get("data", [])
    info = data.get("response", {}).get("dataInfo", {})
    log.info("filemaker.get_records.done", layout=layout, count=len(records))
    return {"records": records, "count": len(records), "data_info": info}


@register_node("filemaker.create_record")
async def create_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new record in a FileMaker layout."""
    layout = config.get("layout") or input_data.get("layout")
    if not layout:
        raise ValueError("'layout' is required in config or input_data")

    field_data = config.get("field_data") or input_data.get("field_data") or {}
    portal_data = config.get("portal_data") or input_data.get("portal_data")

    body: dict = {"fieldData": field_data}
    if portal_data:
        body["portalData"] = portal_data

    log.info("filemaker.create_record", layout=layout, fields=list(field_data.keys()))

    async with (await _client(credential_id, db))[0] as client:
        r = await client.post(f"/layouts/{layout}/records", json=body)
        _raise_for_status(r)
        data = r.json()

    record_id = data.get("response", {}).get("recordId")
    mod_id = data.get("response", {}).get("modId")
    log.info("filemaker.create_record.done", layout=layout, record_id=record_id)
    return {"record_id": record_id, "mod_id": mod_id, "layout": layout}


@register_node("filemaker.update_record")
async def update_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Update an existing record in a FileMaker layout."""
    layout = config.get("layout") or input_data.get("layout")
    record_id = config.get("record_id") or input_data.get("record_id")
    if not layout:
        raise ValueError("'layout' is required")
    if not record_id:
        raise ValueError("'record_id' is required")

    field_data = config.get("field_data") or input_data.get("field_data") or {}
    portal_data = config.get("portal_data") or input_data.get("portal_data")
    mod_id = config.get("mod_id") or input_data.get("mod_id")

    body: dict = {"fieldData": field_data}
    if portal_data:
        body["portalData"] = portal_data
    if mod_id:
        body["modId"] = str(mod_id)

    log.info("filemaker.update_record", layout=layout, record_id=record_id)

    async with (await _client(credential_id, db))[0] as client:
        r = await client.patch(f"/layouts/{layout}/records/{record_id}", json=body)
        _raise_for_status(r)
        data = r.json()

    new_mod_id = data.get("response", {}).get("modId")
    log.info("filemaker.update_record.done", layout=layout, record_id=record_id)
    return {"record_id": record_id, "mod_id": new_mod_id, "layout": layout}


@register_node("filemaker.delete_record")
async def delete_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Delete a record from a FileMaker layout."""
    layout = config.get("layout") or input_data.get("layout")
    record_id = config.get("record_id") or input_data.get("record_id")
    if not layout:
        raise ValueError("'layout' is required")
    if not record_id:
        raise ValueError("'record_id' is required")

    log.info("filemaker.delete_record", layout=layout, record_id=record_id)

    async with (await _client(credential_id, db))[0] as client:
        r = await client.delete(f"/layouts/{layout}/records/{record_id}")
        _raise_for_status(r)

    log.info("filemaker.delete_record.done", layout=layout, record_id=record_id)
    return {"deleted": True, "record_id": record_id, "layout": layout}


@register_node("filemaker.find_records")
async def find_records(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Perform a FileMaker find (search) request against a layout."""
    layout = config.get("layout") or input_data.get("layout")
    if not layout:
        raise ValueError("'layout' is required")

    # query is a list of dicts, e.g. [{"Name": "=John", "Status": "Active"}]
    query = config.get("query") or input_data.get("query")
    if not query:
        raise ValueError("'query' is required — list of field/value dicts")

    limit = int(config.get("limit", 100))
    offset = int(config.get("offset", 1))
    sort_field = config.get("sort_field")
    sort_order = config.get("sort_order", "ascend")

    body: dict = {"query": query, "limit": str(limit), "offset": str(offset)}
    if sort_field:
        body["sort"] = [{"fieldName": sort_field, "sortOrder": sort_order}]

    log.info("filemaker.find_records", layout=layout, query=query)

    async with (await _client(credential_id, db))[0] as client:
        r = await client.post(f"/layouts/{layout}/_find", json=body)
        if r.status_code == 401:
            # FileMaker returns 401 when no records match — treat as empty
            log.info("filemaker.find_records.no_results", layout=layout)
            return {"records": [], "count": 0}
        _raise_for_status(r)
        data = r.json()

    records = data.get("response", {}).get("data", [])
    info = data.get("response", {}).get("dataInfo", {})
    log.info("filemaker.find_records.done", layout=layout, count=len(records))
    return {"records": records, "count": len(records), "data_info": info}
