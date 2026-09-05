"""PocketBase self-hosted backend integration — collections and records."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _headers(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@register_node("pocketbase.list_records")
async def pocketbase_list_records(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List records from a PocketBase collection.

    config:
      base_url     — PocketBase base URL, e.g. "https://myapp.pockethost.io" (required)
      admin_token  — admin auth token (required)
      collection   — collection name (required)
      page         — page number (default 1)
      per_page     — records per page (default 25)
    """
    base_url = config.get("base_url") or input_data.get("base_url")
    admin_token = config.get("admin_token") or input_data.get("admin_token")
    if not base_url or not admin_token:
        raise ValueError("base_url and admin_token are required for pocketbase.list_records")

    collection = config.get("collection") or input_data.get("collection")
    if not collection:
        raise ValueError("collection is required for pocketbase.list_records")

    page = int(config.get("page", 1))
    per_page = int(config.get("per_page", 25))

    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
        r = await client.get(
            f"/api/collections/{collection}/records",
            params={"page": page, "perPage": per_page},
            headers=_headers(admin_token),
        )
        r.raise_for_status()
        data = r.json()

    items = data.get("items", [])
    total = data.get("totalItems", len(items))
    log.info("pocketbase.list_records", collection=collection, count=len(items))
    return {"records": items, "count": len(items), "total": total, "page": page}


@register_node("pocketbase.create_record")
async def pocketbase_create_record(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a record in a PocketBase collection.

    config/input_data:
      base_url    — PocketBase base URL (required)
      admin_token — admin auth token (required)
      collection  — collection name (required)
      data        — dict of field values (required)
    """
    base_url = config.get("base_url") or input_data.get("base_url")
    admin_token = config.get("admin_token") or input_data.get("admin_token")
    if not base_url or not admin_token:
        raise ValueError("base_url and admin_token are required for pocketbase.create_record")

    collection = config.get("collection") or input_data.get("collection")
    data_payload = config.get("data") or input_data.get("data") or {}
    if not collection:
        raise ValueError("collection is required for pocketbase.create_record")

    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
        r = await client.post(
            f"/api/collections/{collection}/records",
            json=data_payload,
            headers=_headers(admin_token),
        )
        r.raise_for_status()
        record = r.json()

    log.info("pocketbase.create_record", collection=collection, record_id=record.get("id"))
    return {"record": record, "record_id": record.get("id")}


@register_node("pocketbase.update_record")
async def pocketbase_update_record(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update a PocketBase record by ID.

    config/input_data:
      base_url    — PocketBase base URL (required)
      admin_token — admin auth token (required)
      collection  — collection name (required)
      record_id   — record ID to update (required)
      data        — dict of fields to update (required)
    """
    base_url = config.get("base_url") or input_data.get("base_url")
    admin_token = config.get("admin_token") or input_data.get("admin_token")
    if not base_url or not admin_token:
        raise ValueError("base_url and admin_token are required for pocketbase.update_record")

    collection = config.get("collection") or input_data.get("collection")
    record_id = config.get("record_id") or input_data.get("record_id")
    data_payload = config.get("data") or input_data.get("data") or {}
    if not collection or not record_id:
        raise ValueError("collection and record_id are required for pocketbase.update_record")

    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
        r = await client.patch(
            f"/api/collections/{collection}/records/{record_id}",
            json=data_payload,
            headers=_headers(admin_token),
        )
        r.raise_for_status()
        record = r.json()

    log.info("pocketbase.update_record", collection=collection, record_id=record_id)
    return {"record": record, "record_id": record_id}


@register_node("pocketbase.delete_record")
async def pocketbase_delete_record(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete a PocketBase record by ID.

    config/input_data:
      base_url    — PocketBase base URL (required)
      admin_token — admin auth token (required)
      collection  — collection name (required)
      record_id   — record ID to delete (required)
    """
    base_url = config.get("base_url") or input_data.get("base_url")
    admin_token = config.get("admin_token") or input_data.get("admin_token")
    if not base_url or not admin_token:
        raise ValueError("base_url and admin_token are required for pocketbase.delete_record")

    collection = config.get("collection") or input_data.get("collection")
    record_id = config.get("record_id") or input_data.get("record_id")
    if not collection or not record_id:
        raise ValueError("collection and record_id are required for pocketbase.delete_record")

    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
        r = await client.delete(
            f"/api/collections/{collection}/records/{record_id}",
            headers=_headers(admin_token),
        )
        r.raise_for_status()

    log.info("pocketbase.delete_record", collection=collection, record_id=record_id)
    return {"success": True, "record_id": record_id, "collection": collection}
