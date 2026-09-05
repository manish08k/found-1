"""
Adalo no-code app platform integration.

Provides CRUD operations against Adalo database collections
via the Adalo REST API v0.

Credential fields:
  - api_key : Adalo API key

Auth: Bearer token.
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://api.adalo.com/v0/apps"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Adalo credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
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
        raise ValueError(f"Adalo API error {r.status_code}: {detail}")


def _collection_url(app_id: str, collection_id: str) -> str:
    return f"/{app_id}/collections/{collection_id}"


@register_node("adalo.list_records")
async def adalo_list_records(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List records from an Adalo collection with optional filtering and pagination."""
    app_id = config.get("app_id") or input_data.get("app_id")
    collection_id = config.get("collection_id") or input_data.get("collection_id")

    if not app_id:
        raise ValueError("adalo.list_records requires 'app_id'")
    if not collection_id:
        raise ValueError("adalo.list_records requires 'collection_id'")

    limit = int(config.get("limit") or input_data.get("limit", 25))
    offset = int(config.get("offset") or input_data.get("offset", 0))
    filter_where = config.get("where") or input_data.get("where")

    params: dict = {"limit": limit, "offset": offset}
    if filter_where:
        # Adalo accepts JSON-encoded filter strings
        import json as _json
        params["where"] = _json.dumps(filter_where) if isinstance(filter_where, dict) else filter_where

    async with await _client(credential_id, db) as client:
        url = _collection_url(app_id, collection_id)
        r = await client.get(url, params=params)
        _raise_for_status(r)
        data = r.json()

    records = data.get("records", data if isinstance(data, list) else [])
    return {
        "records": records,
        "count": len(records),
        "offset": offset,
    }


@register_node("adalo.create_record")
async def adalo_create_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new record in an Adalo collection."""
    app_id = config.get("app_id") or input_data.get("app_id")
    collection_id = config.get("collection_id") or input_data.get("collection_id")

    if not app_id:
        raise ValueError("adalo.create_record requires 'app_id'")
    if not collection_id:
        raise ValueError("adalo.create_record requires 'collection_id'")

    # Merge explicit fields from config and input_data (input_data wins on conflict)
    fields = {
        k: v for k, v in config.items()
        if k not in ("app_id", "collection_id")
    }
    fields.update({
        k: v for k, v in input_data.items()
        if k not in ("app_id", "collection_id")
    })

    if not fields:
        raise ValueError("adalo.create_record requires at least one field to set")

    async with await _client(credential_id, db) as client:
        url = _collection_url(app_id, collection_id)
        r = await client.post(url, json=fields)
        _raise_for_status(r)
        record = r.json()

    log.info("adalo.create_record", app_id=app_id, collection_id=collection_id, record_id=record.get("id"))
    return {"record": record, "record_id": record.get("id")}


@register_node("adalo.update_record")
async def adalo_update_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Update an existing record in an Adalo collection."""
    app_id = config.get("app_id") or input_data.get("app_id")
    collection_id = config.get("collection_id") or input_data.get("collection_id")
    record_id = config.get("record_id") or input_data.get("record_id")

    if not app_id:
        raise ValueError("adalo.update_record requires 'app_id'")
    if not collection_id:
        raise ValueError("adalo.update_record requires 'collection_id'")
    if not record_id:
        raise ValueError("adalo.update_record requires 'record_id'")

    fields = {
        k: v for k, v in config.items()
        if k not in ("app_id", "collection_id", "record_id")
    }
    fields.update({
        k: v for k, v in input_data.items()
        if k not in ("app_id", "collection_id", "record_id")
    })

    if not fields:
        raise ValueError("adalo.update_record requires at least one field to update")

    async with await _client(credential_id, db) as client:
        url = f"{_collection_url(app_id, collection_id)}/{record_id}"
        r = await client.put(url, json=fields)
        _raise_for_status(r)
        record = r.json()

    log.info("adalo.update_record", app_id=app_id, collection_id=collection_id, record_id=record_id)
    return {"record": record, "record_id": record_id, "updated": True}


@register_node("adalo.delete_record")
async def adalo_delete_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Delete a record from an Adalo collection by its ID."""
    app_id = config.get("app_id") or input_data.get("app_id")
    collection_id = config.get("collection_id") or input_data.get("collection_id")
    record_id = config.get("record_id") or input_data.get("record_id")

    if not app_id:
        raise ValueError("adalo.delete_record requires 'app_id'")
    if not collection_id:
        raise ValueError("adalo.delete_record requires 'collection_id'")
    if not record_id:
        raise ValueError("adalo.delete_record requires 'record_id'")

    async with await _client(credential_id, db) as client:
        url = f"{_collection_url(app_id, collection_id)}/{record_id}"
        r = await client.delete(url)
        _raise_for_status(r)

    log.info("adalo.delete_record", app_id=app_id, collection_id=collection_id, record_id=record_id)
    return {"deleted": True, "record_id": record_id}


@register_node("adalo.get_record")
async def adalo_get_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve a single record from an Adalo collection by its ID."""
    app_id = config.get("app_id") or input_data.get("app_id")
    collection_id = config.get("collection_id") or input_data.get("collection_id")
    record_id = config.get("record_id") or input_data.get("record_id")

    if not app_id:
        raise ValueError("adalo.get_record requires 'app_id'")
    if not collection_id:
        raise ValueError("adalo.get_record requires 'collection_id'")
    if not record_id:
        raise ValueError("adalo.get_record requires 'record_id'")

    async with await _client(credential_id, db) as client:
        url = f"{_collection_url(app_id, collection_id)}/{record_id}"
        r = await client.get(url)
        _raise_for_status(r)
        record = r.json()

    return {"record": record}
