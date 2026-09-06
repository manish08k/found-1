"""APITable integration — datasheets, records, and spaces."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

APITABLE_BASE = "https://api.apitable.com/fusion/v1"


def _apitable_headers(api_token: str) -> dict:
    return {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}


@register_node("apitable.list_spaces")
async def apitable_list_spaces(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all spaces available to the authenticated user.

    config:
      api_token — APITable API bearer token (required)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")

    async with httpx.AsyncClient(base_url=APITABLE_BASE, timeout=30) as client:
        r = await client.get("/spaces", headers=_apitable_headers(api_token))
        r.raise_for_status()
        data = r.json()

    spaces = data.get("data", {}).get("spaces", [])
    log.info("apitable.list_spaces", count=len(spaces))
    return {"spaces": spaces, "count": len(spaces)}


@register_node("apitable.list_datasheets")
async def apitable_list_datasheets(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all datasheets (nodes) in a space.

    config:
      api_token — APITable API bearer token (required)
      space_id  — space ID to list datasheets in (required)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    space_id = merged.get("space_id")
    if not space_id:
        raise ValueError("space_id is required for apitable.list_datasheets")

    async with httpx.AsyncClient(base_url=APITABLE_BASE, timeout=30) as client:
        r = await client.get(f"/spaces/{space_id}/nodes", headers=_apitable_headers(api_token))
        r.raise_for_status()
        data = r.json()

    nodes = data.get("data", {}).get("nodes", [])
    log.info("apitable.list_datasheets", space_id=space_id, count=len(nodes))
    return {"nodes": nodes, "count": len(nodes), "space_id": space_id}


@register_node("apitable.get_records")
async def apitable_get_records(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get records from an APITable datasheet.

    config:
      api_token    — APITable API bearer token (required)
      datasheet_id — datasheet ID (required)
      page_num     — page number (optional, default 1)
      page_size    — records per page (optional, default 100)
      view_id      — view ID to filter by (optional)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    datasheet_id = merged.get("datasheet_id")
    if not datasheet_id:
        raise ValueError("datasheet_id is required for apitable.get_records")

    params: dict = {
        "pageNum": merged.get("page_num", 1),
        "pageSize": merged.get("page_size", 100),
    }
    if merged.get("view_id"):
        params["viewId"] = merged["view_id"]

    async with httpx.AsyncClient(base_url=APITABLE_BASE, timeout=30) as client:
        r = await client.get(
            f"/datasheets/{datasheet_id}/records",
            headers=_apitable_headers(api_token),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    records = data.get("data", {}).get("records", [])
    log.info("apitable.get_records", datasheet_id=datasheet_id, count=len(records))
    return {"records": records, "count": len(records), "datasheet_id": datasheet_id}


@register_node("apitable.create_record")
async def apitable_create_record(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new record in an APITable datasheet.

    config:
      api_token    — APITable API bearer token (required)
      datasheet_id — datasheet ID (required)
      fields       — dict of field name -> value (required)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    datasheet_id = merged.get("datasheet_id")
    fields = merged.get("fields", {})
    if not datasheet_id:
        raise ValueError("datasheet_id is required for apitable.create_record")

    payload = {"records": [{"fields": fields}]}

    async with httpx.AsyncClient(base_url=APITABLE_BASE, timeout=30) as client:
        r = await client.post(
            f"/datasheets/{datasheet_id}/records",
            headers=_apitable_headers(api_token),
            json=payload,
        )
        r.raise_for_status()
        data = r.json()

    records = data.get("data", {}).get("records", [])
    record_id = records[0].get("recordId") if records else None
    log.info("apitable.create_record", datasheet_id=datasheet_id, record_id=record_id)
    return {"records": records, "record_id": record_id, "datasheet_id": datasheet_id}


@register_node("apitable.update_record")
async def apitable_update_record(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update an existing record in an APITable datasheet.

    config:
      api_token    — APITable API bearer token (required)
      datasheet_id — datasheet ID (required)
      record_id    — record ID to update (required)
      fields       — dict of field name -> new value (required)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    datasheet_id = merged.get("datasheet_id")
    record_id = merged.get("record_id")
    fields = merged.get("fields", {})
    if not datasheet_id or not record_id:
        raise ValueError("datasheet_id and record_id are required for apitable.update_record")

    payload = {"records": [{"recordId": record_id, "fields": fields}]}

    async with httpx.AsyncClient(base_url=APITABLE_BASE, timeout=30) as client:
        r = await client.patch(
            f"/datasheets/{datasheet_id}/records",
            headers=_apitable_headers(api_token),
            json=payload,
        )
        r.raise_for_status()
        data = r.json()

    log.info("apitable.update_record", datasheet_id=datasheet_id, record_id=record_id)
    return {"records": data.get("data", {}).get("records", []), "record_id": record_id}


@register_node("apitable.delete_record")
async def apitable_delete_record(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete a record from an APITable datasheet.

    config:
      api_token    — APITable API bearer token (required)
      datasheet_id — datasheet ID (required)
      record_id    — record ID to delete (required)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    datasheet_id = merged.get("datasheet_id")
    record_id = merged.get("record_id")
    if not datasheet_id or not record_id:
        raise ValueError("datasheet_id and record_id are required for apitable.delete_record")

    async with httpx.AsyncClient(base_url=APITABLE_BASE, timeout=30) as client:
        r = await client.delete(
            f"/datasheets/{datasheet_id}/records",
            headers=_apitable_headers(api_token),
            params={"recordIds": record_id},
        )
        r.raise_for_status()

    log.info("apitable.delete_record", datasheet_id=datasheet_id, record_id=record_id)
    return {"success": True, "record_id": record_id, "datasheet_id": datasheet_id}
