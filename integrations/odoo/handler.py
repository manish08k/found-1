"""
Odoo ERP integration via JSON-RPC.

Auth: Odoo JSON-RPC session login (db + username + api_key / password).

Credential fields:
  - base_url: Odoo instance URL (e.g. https://mycompany.odoo.com)
  - db:       Odoo database name
  - username: Odoo user login (email)
  - api_key:  Odoo API key (or password)

Nodes:
  - odoo.search_records  — search + read records from any model
  - odoo.create_record   — create a new record
  - odoo.update_record   — write fields on existing record(s)
  - odoo.delete_record   — unlink (delete) record(s)
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _get_creds(credential_id: str, db) -> dict:
    creds = await get_credential_data(credential_id, db)
    for field in ("base_url", "db", "username", "api_key"):
        if not creds.get(field):
            raise ValueError(f"Odoo credential missing '{field}'")
    return creds


async def _authenticate(client: httpx.AsyncClient, creds: dict) -> int:
    """Authenticate and return the Odoo uid."""
    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "id": 1,
        "params": {
            "db": creds["db"],
            "login": creds["username"],
            "password": creds["api_key"],
        },
    }
    base_url = creds["base_url"].rstrip("/")
    r = await client.post(f"{base_url}/web/session/authenticate", json=payload)
    if not r.is_success:
        raise ValueError(f"Odoo auth failed HTTP {r.status_code}: {r.text[:200]}")
    result = r.json()
    uid = (result.get("result") or {}).get("uid")
    if not uid:
        error = result.get("error") or result.get("result", {})
        raise ValueError(f"Odoo authentication failed: {error}")
    return uid


async def _call_kw(
    client: httpx.AsyncClient,
    creds: dict,
    uid: int,
    model: str,
    method: str,
    args: list,
    kwargs: dict | None = None,
) -> dict:
    """Execute an Odoo JSON-RPC call_kw request."""
    base_url = creds["base_url"].rstrip("/")
    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "id": 2,
        "params": {
            "model": model,
            "method": method,
            "args": args,
            "kwargs": kwargs or {},
        },
    }
    r = await client.post(f"{base_url}/web/dataset/call_kw", json=payload)
    if not r.is_success:
        raise ValueError(f"Odoo call_kw HTTP {r.status_code}: {r.text[:200]}")
    body = r.json()
    if "error" in body:
        raise ValueError(f"Odoo RPC error: {body['error']}")
    return body.get("result", {})


@register_node("odoo.search_records")
async def search_records(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    search_read on any Odoo model.

    Config:
      model   — (required) Odoo model name (e.g. res.partner)
      domain  — Odoo domain list (default: [])
      fields  — list of field names to return (default: all)
      limit   — max records (default: 80)
      offset  — pagination offset
      order   — sort string (e.g. "name asc")
    """
    model = config.get("model") or input_data.get("model")
    if not model:
        raise ValueError("odoo.search_records requires 'model'")
    domain = config.get("domain") or input_data.get("domain") or []
    fields = config.get("fields") or input_data.get("fields") or []
    limit = config.get("limit") or input_data.get("limit") or 80
    offset = config.get("offset") or input_data.get("offset") or 0
    order = config.get("order") or input_data.get("order") or ""

    log.info("odoo.search_records", model=model, domain=domain, limit=limit)
    creds = await _get_creds(credential_id, db)
    async with httpx.AsyncClient(timeout=30.0) as client:
        uid = await _authenticate(client, creds)
        result = await _call_kw(
            client, creds, uid, model, "search_read",
            [domain],
            {"fields": fields, "limit": limit, "offset": offset, "order": order},
        )
    return {"records": result if isinstance(result, list) else [result]}


@register_node("odoo.create_record")
async def create_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    create on any Odoo model.

    Config:
      model  — (required) Odoo model name
      values — (required) dict of field values
    """
    model = config.get("model") or input_data.get("model")
    values = config.get("values") or input_data.get("values")
    if not model:
        raise ValueError("odoo.create_record requires 'model'")
    if not values or not isinstance(values, dict):
        raise ValueError("odoo.create_record requires 'values' dict")

    log.info("odoo.create_record", model=model)
    creds = await _get_creds(credential_id, db)
    async with httpx.AsyncClient(timeout=30.0) as client:
        uid = await _authenticate(client, creds)
        record_id = await _call_kw(client, creds, uid, model, "create", [values])
    return {"id": record_id, "model": model}


@register_node("odoo.update_record")
async def update_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    write on any Odoo model.

    Config:
      model   — (required) Odoo model name
      ids     — (required) list of record IDs to update
      values  — (required) dict of field values to set
    """
    model = config.get("model") or input_data.get("model")
    ids = config.get("ids") or input_data.get("ids")
    values = config.get("values") or input_data.get("values")
    if not model:
        raise ValueError("odoo.update_record requires 'model'")
    if not ids:
        raise ValueError("odoo.update_record requires 'ids' list")
    if not values or not isinstance(values, dict):
        raise ValueError("odoo.update_record requires 'values' dict")
    if isinstance(ids, int):
        ids = [ids]

    log.info("odoo.update_record", model=model, ids=ids)
    creds = await _get_creds(credential_id, db)
    async with httpx.AsyncClient(timeout=30.0) as client:
        uid = await _authenticate(client, creds)
        result = await _call_kw(client, creds, uid, model, "write", [ids, values])
    return {"success": bool(result), "ids": ids, "model": model}


@register_node("odoo.delete_record")
async def delete_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    unlink on any Odoo model.

    Config:
      model — (required) Odoo model name
      ids   — (required) list of record IDs to delete
    """
    model = config.get("model") or input_data.get("model")
    ids = config.get("ids") or input_data.get("ids")
    if not model:
        raise ValueError("odoo.delete_record requires 'model'")
    if not ids:
        raise ValueError("odoo.delete_record requires 'ids' list")
    if isinstance(ids, int):
        ids = [ids]

    log.info("odoo.delete_record", model=model, ids=ids)
    creds = await _get_creds(credential_id, db)
    async with httpx.AsyncClient(timeout=30.0) as client:
        uid = await _authenticate(client, creds)
        result = await _call_kw(client, creds, uid, model, "unlink", [ids])
    return {"success": bool(result), "ids": ids, "model": model}


async def test_connection(creds: dict) -> None:
    """Verify Odoo credentials by authenticating and listing databases."""
    for field in ("base_url", "db", "username", "api_key"):
        if not creds.get(field):
            raise ValueError(f"Odoo requires '{field}'")
    async with httpx.AsyncClient(timeout=15.0) as client:
        await _authenticate(client, creds)
