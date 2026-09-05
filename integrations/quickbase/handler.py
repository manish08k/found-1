"""
QuickBase low-code platform integration.

Provides record CRUD operations against QuickBase application tables
via the QuickBase REST API v1.

Credential fields:
  - realm_hostname : QuickBase realm hostname (e.g. 'mycompany.quickbase.com').
  - user_token     : QuickBase user token (found in My Profile > User Token Manager).

Auth: user_token sent in QB-USER-TOKEN header.
Base URL: https://api.quickbase.com/v1/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.quickbase.com/v1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    realm_hostname = creds.get("realm_hostname")
    user_token = creds.get("user_token")
    if not realm_hostname:
        raise ValueError("QuickBase credential missing 'realm_hostname'")
    if not user_token:
        raise ValueError("QuickBase credential missing 'user_token'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "QB-Realm-Hostname": realm_hostname,
            "QB-USER-TOKEN": user_token,
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"QuickBase API error {r.status_code}: {detail}")


@register_node("quickbase.list_records")
async def quickbase_list_records(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Query and list records from a QuickBase table.

    Params:
      - table_id (required): The QuickBase table DBID (e.g. 'bck7gp3q2').
      - select: List of field IDs (integers) to return. Omit for all fields.
      - where: QuickBase query string to filter records (e.g. "{6.EX.'value'}").
      - sort_by: List of sort dicts, e.g. [{"fieldId": 6, "order": "ASC"}].
      - group_by: List of group-by dicts, e.g. [{"fieldId": 6, "grouping": "equal-values"}].
      - options: Dict with pagination options, e.g. {"skip": 0, "top": 100}.
    """
    table_id = config.get("table_id") or input_data.get("table_id")
    if not table_id:
        raise ValueError("quickbase.list_records requires 'table_id'")

    payload: dict = {"from": table_id}

    select = config.get("select") or input_data.get("select")
    if select:
        payload["select"] = select if isinstance(select, list) else [int(x) for x in str(select).split(",") if x.strip()]

    where = config.get("where") or input_data.get("where")
    if where:
        payload["where"] = where

    sort_by = config.get("sort_by") or input_data.get("sort_by")
    if sort_by:
        payload["sortBy"] = sort_by

    group_by = config.get("group_by") or input_data.get("group_by")
    if group_by:
        payload["groupBy"] = group_by

    options = config.get("options") or input_data.get("options")
    if options:
        payload["options"] = options

    async with await _client(credential_id, db) as client:
        r = await client.post("/records/query", json=payload)
        _raise_for_status(r)
        data = r.json()

    records = data.get("data", [])
    log.info("quickbase.list_records", table_id=table_id, count=len(records))
    return {
        "records": records,
        "fields": data.get("fields", []),
        "metadata": data.get("metadata", {}),
    }


@register_node("quickbase.create_record")
async def quickbase_create_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Create one or more records in a QuickBase table.

    Params:
      - table_id (required): The QuickBase table DBID.
      - data (required): List of record dicts. Each dict maps field ID (str/int)
        to {"value": <value>}.
        Example: [{"6": {"value": "Hello"}, "7": {"value": 42}}]
      - fields_to_return: List of field IDs to return in the response.
    """
    table_id = config.get("table_id") or input_data.get("table_id")
    if not table_id:
        raise ValueError("quickbase.create_record requires 'table_id'")

    data_rows = config.get("data") or input_data.get("data")
    if not data_rows:
        raise ValueError("quickbase.create_record requires 'data'")

    if isinstance(data_rows, dict):
        data_rows = [data_rows]

    payload: dict = {"to": table_id, "data": data_rows}

    fields_to_return = config.get("fields_to_return") or input_data.get("fields_to_return")
    if fields_to_return:
        payload["fieldsToReturn"] = fields_to_return if isinstance(fields_to_return, list) else [int(x) for x in str(fields_to_return).split(",") if x.strip()]

    async with await _client(credential_id, db) as client:
        r = await client.post("/records", json=payload)
        _raise_for_status(r)
        resp = r.json()

    log.info("quickbase.create_record", table_id=table_id, created=len(resp.get("metadata", {}).get("createdRecordIds", [])))
    return {
        "metadata": resp.get("metadata", {}),
        "created_record_ids": resp.get("metadata", {}).get("createdRecordIds", []),
        "response": resp,
    }


@register_node("quickbase.update_record")
async def quickbase_update_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Update one or more existing records in a QuickBase table.

    Params:
      - table_id (required): The QuickBase table DBID.
      - data (required): List of record dicts. Each dict MUST include the key
        field (record ID in field 3 by default):
        [{"3": {"value": 1}, "6": {"value": "Updated"}}]
      - fields_to_return: List of field IDs to return in the response.
    """
    table_id = config.get("table_id") or input_data.get("table_id")
    if not table_id:
        raise ValueError("quickbase.update_record requires 'table_id'")

    data_rows = config.get("data") or input_data.get("data")
    if not data_rows:
        raise ValueError("quickbase.update_record requires 'data'")

    if isinstance(data_rows, dict):
        data_rows = [data_rows]

    payload: dict = {"to": table_id, "data": data_rows}

    fields_to_return = config.get("fields_to_return") or input_data.get("fields_to_return")
    if fields_to_return:
        payload["fieldsToReturn"] = fields_to_return if isinstance(fields_to_return, list) else [int(x) for x in str(fields_to_return).split(",") if x.strip()]

    async with await _client(credential_id, db) as client:
        r = await client.post("/records", json=payload)
        _raise_for_status(r)
        resp = r.json()

    log.info("quickbase.update_record", table_id=table_id, updated=len(resp.get("metadata", {}).get("updatedRecordIds", [])))
    return {
        "metadata": resp.get("metadata", {}),
        "updated_record_ids": resp.get("metadata", {}).get("updatedRecordIds", []),
        "response": resp,
    }


@register_node("quickbase.delete_record")
async def quickbase_delete_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Delete records from a QuickBase table matching a query.

    Params:
      - table_id (required): The QuickBase table DBID.
      - where (required): QuickBase query string identifying records to delete
        (e.g. "{3.EX.'5'}" to delete record with ID 5).
        WARNING: Omitting 'where' may delete ALL records — always supply a filter.
    """
    table_id = config.get("table_id") or input_data.get("table_id")
    if not table_id:
        raise ValueError("quickbase.delete_record requires 'table_id'")

    where = config.get("where") or input_data.get("where")
    if not where:
        raise ValueError("quickbase.delete_record requires 'where' to avoid accidentally deleting all records")

    payload: dict = {"from": table_id, "where": where}

    async with await _client(credential_id, db) as client:
        r = await client.delete("/records", json=payload)
        _raise_for_status(r)
        resp = r.json()

    deleted = resp.get("numberDeleted", 0)
    log.info("quickbase.delete_record", table_id=table_id, deleted=deleted)
    return {
        "number_deleted": deleted,
        "response": resp,
    }
