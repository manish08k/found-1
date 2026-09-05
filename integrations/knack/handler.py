"""Knack database app integration — records management."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

KNACK_BASE = "https://api.knack.com/v1"


def _headers(app_id: str, api_key: str) -> dict:
    return {
        "X-Knack-Application-Id": app_id,
        "X-Knack-REST-API-Key": api_key,
        "Content-Type": "application/json",
    }


@register_node("knack.get_objects")
async def knack_get_objects(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Retrieve records from a Knack object (table).

    config:
      app_id        — Knack application ID (required)
      api_key       — Knack REST API key (required)
      object_id     — object key, e.g. "object_1" (required)
      rows_per_page — number of records per page (default 25)
    """
    app_id = config.get("app_id") or input_data.get("app_id")
    api_key = config.get("api_key") or input_data.get("api_key")
    if not app_id or not api_key:
        raise ValueError("app_id and api_key are required for knack.get_objects")

    object_id = config.get("object_id") or input_data.get("object_id", "object_1")
    rows_per_page = int(config.get("rows_per_page", 25))

    async with httpx.AsyncClient(base_url=KNACK_BASE, timeout=30) as client:
        r = await client.get(
            f"/objects/{object_id}/records",
            params={"rows_per_page": rows_per_page},
            headers=_headers(app_id, api_key),
        )
        r.raise_for_status()
        data = r.json()

    records = data.get("records", [])
    total = data.get("total_records", len(records))
    log.info("knack.get_objects", object_id=object_id, count=len(records))
    return {"records": records, "count": len(records), "total": total}


@register_node("knack.create_record")
async def knack_create_record(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a record in a Knack object.

    config/input_data:
      app_id    — Knack application ID (required)
      api_key   — Knack REST API key (required)
      object_id — object key, e.g. "object_1" (required)
      data      — dict of {field_key: value} pairs to set (required)
    """
    app_id = config.get("app_id") or input_data.get("app_id")
    api_key = config.get("api_key") or input_data.get("api_key")
    if not app_id or not api_key:
        raise ValueError("app_id and api_key are required for knack.create_record")

    object_id = config.get("object_id") or input_data.get("object_id", "object_1")
    data_payload = config.get("data") or input_data.get("data") or {}

    async with httpx.AsyncClient(base_url=KNACK_BASE, timeout=30) as client:
        r = await client.post(
            f"/objects/{object_id}/records",
            json=data_payload,
            headers=_headers(app_id, api_key),
        )
        r.raise_for_status()
        record = r.json()

    log.info("knack.create_record", object_id=object_id, record_id=record.get("id"))
    return {"record": record, "record_id": record.get("id")}


@register_node("knack.update_record")
async def knack_update_record(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update an existing Knack record by ID.

    config/input_data:
      app_id    — Knack application ID (required)
      api_key   — Knack REST API key (required)
      object_id — object key, e.g. "object_1" (required)
      record_id — record ID to update (required)
      data      — dict of {field_key: value} pairs to update (required)
    """
    app_id = config.get("app_id") or input_data.get("app_id")
    api_key = config.get("api_key") or input_data.get("api_key")
    if not app_id or not api_key:
        raise ValueError("app_id and api_key are required for knack.update_record")

    object_id = config.get("object_id") or input_data.get("object_id", "object_1")
    record_id = config.get("record_id") or input_data.get("record_id")
    data_payload = config.get("data") or input_data.get("data") or {}
    if not record_id:
        raise ValueError("record_id is required for knack.update_record")

    async with httpx.AsyncClient(base_url=KNACK_BASE, timeout=30) as client:
        r = await client.put(
            f"/objects/{object_id}/records/{record_id}",
            json=data_payload,
            headers=_headers(app_id, api_key),
        )
        r.raise_for_status()
        record = r.json()

    log.info("knack.update_record", object_id=object_id, record_id=record_id)
    return {"record": record, "record_id": record_id}
