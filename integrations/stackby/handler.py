"""Stackby integration — spreadsheet database (API key auth)."""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

STACKBY_BASE = "https://stackby.com/api/betav1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds["api_key"]
    return httpx.AsyncClient(
        headers={"api-key": api_key, "Content-Type": "application/json"},
        timeout=30,
    )


@register_node("stackby.list_records")
async def stackby_list_records(config: dict, input_data: dict, credential_id: str, db) -> dict:
    creds = await get_credential_data(credential_id, db)
    stack_id = config.get("stack_id") or creds.get("stack_id") or input_data.get("stack_id", "")
    table_name = config.get("table_name") or input_data.get("table_name", "")
    row_limit = config.get("row_limit", 100)
    row_offset = config.get("row_offset", 0)

    params = {"stackId": stack_id, "tableId": table_name,
               "rowLimit": row_limit, "rowOffset": row_offset}

    log.info("stackby.list_records", stack_id=stack_id, table=table_name)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"{STACKBY_BASE}/rowlist", params=params)
        r.raise_for_status()
        data = r.json()

    return {"records": data.get("data", data), "stack_id": stack_id, "table_name": table_name}


@register_node("stackby.create_record")
async def stackby_create_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    creds = await get_credential_data(credential_id, db)
    stack_id = config.get("stack_id") or creds.get("stack_id") or input_data.get("stack_id", "")
    table_name = config.get("table_name") or input_data.get("table_name", "")
    fields = config.get("fields") or input_data.get("fields", {})

    payload = {"stackId": stack_id, "tableId": table_name, "data": [fields]}

    log.info("stackby.create_record", stack_id=stack_id, table=table_name)
    async with await _client(credential_id, db) as client:
        r = await client.post(f"{STACKBY_BASE}/rowcreate", json=payload)
        r.raise_for_status()
        data = r.json()

    return {"record": data.get("data", data), "stack_id": stack_id, "table_name": table_name}


@register_node("stackby.update_record")
async def stackby_update_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    creds = await get_credential_data(credential_id, db)
    stack_id = config.get("stack_id") or creds.get("stack_id") or input_data.get("stack_id", "")
    table_name = config.get("table_name") or input_data.get("table_name", "")
    row_id = config.get("row_id") or input_data.get("row_id", "")
    fields = config.get("fields") or input_data.get("fields", {})

    payload = {"stackId": stack_id, "tableId": table_name, "rowId": row_id, "data": fields}

    log.info("stackby.update_record", stack_id=stack_id, table=table_name, row_id=row_id)
    async with await _client(credential_id, db) as client:
        r = await client.post(f"{STACKBY_BASE}/rowupdate", json=payload)
        r.raise_for_status()
        data = r.json()

    return {"record": data.get("data", data), "row_id": row_id}


@register_node("stackby.delete_record")
async def stackby_delete_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    creds = await get_credential_data(credential_id, db)
    stack_id = config.get("stack_id") or creds.get("stack_id") or input_data.get("stack_id", "")
    table_name = config.get("table_name") or input_data.get("table_name", "")
    row_id = config.get("row_id") or input_data.get("row_id", "")

    payload = {"stackId": stack_id, "tableId": table_name, "rowId": row_id}

    log.info("stackby.delete_record", stack_id=stack_id, table=table_name, row_id=row_id)
    async with await _client(credential_id, db) as client:
        r = await client.post(f"{STACKBY_BASE}/rowdelete", json=payload)
        r.raise_for_status()
        data = r.json()

    return {"deleted": True, "row_id": row_id, "response": data}
