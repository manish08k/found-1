"""Attio CRM integration — records and lists."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

ATTIO_BASE = "https://api.attio.com/v2"


@register_node("attio.list_records")
async def attio_list_records(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List records for a given Attio object (e.g. 'people', 'companies').

    config/input_data:
      api_key   — Attio API key (required)
      object_id — object slug, e.g. 'people' or 'companies' (default 'people')
      limit     — number of records to return (default 25)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    object_id = merged.get("object_id", "people")
    limit = int(merged.get("limit", 25))

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{ATTIO_BASE}/objects/{object_id}/records"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params={"limit": limit})
        r.raise_for_status()
        data = r.json()

    records = data.get("data", data)
    log.info("attio.list_records", object_id=object_id, count=len(records) if isinstance(records, list) else None)
    return {"records": records, "object_id": object_id}


@register_node("attio.create_record")
async def attio_create_record(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new record in an Attio object.

    config/input_data:
      api_key   — Attio API key (required)
      object_id — object slug, e.g. 'people' (required)
      values    — dict of attribute values, e.g. {"name": [{"first_name": "Jane"}]}
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    object_id = merged.get("object_id", "people")
    values = merged.get("values") or {}

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{ATTIO_BASE}/objects/{object_id}/records"
    payload = {"data": {"values": values}}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    record = data.get("data", data)
    log.info("attio.create_record", object_id=object_id)
    return {"record": record, "object_id": object_id}


@register_node("attio.get_record")
async def attio_get_record(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single Attio record by object and record ID.

    config/input_data:
      api_key   — Attio API key (required)
      object_id — object slug, e.g. 'people' (required)
      record_id — record ID (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    object_id = merged.get("object_id") or ""
    record_id = merged.get("record_id") or ""

    if not object_id:
        raise ValueError("object_id is required for attio.get_record")
    if not record_id:
        raise ValueError("record_id is required for attio.get_record")

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{ATTIO_BASE}/objects/{object_id}/records/{record_id}"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()

    record = data.get("data", data)
    log.info("attio.get_record", object_id=object_id, record_id=record_id)
    return {"record": record, "object_id": object_id, "record_id": record_id}


@register_node("attio.list_lists")
async def attio_list_lists(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Attio lists.

    config/input_data:
      api_key — Attio API key (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{ATTIO_BASE}/lists"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()

    lists = data.get("data", data)
    log.info("attio.list_lists", count=len(lists) if isinstance(lists, list) else None)
    return {"lists": lists}
