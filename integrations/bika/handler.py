"""Bika AI-powered automation database — handler for bika integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.bika.ai/v1"


@register_node("bika.list_tables")
async def bika_list_tables(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List tables.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/tables", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("bika.list_tables")
    return {"data": data}

@register_node("bika.list_records")
async def bika_list_records(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List records in a table.

    config/input_data:
      api_key — API key or token (required)
      table_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    table_id = merged.get("table_id") or ""
    if not table_id:
        raise ValueError("table_id required for bika.list_records")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/tables/{table_id}/records", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("bika.list_records")
    return {"data": data}

@register_node("bika.create_record")
async def bika_create_record(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a record.

    config/input_data:
      api_key — API key or token (required)
      table_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    table_id = merged.get("table_id") or ""
    if not table_id:
        raise ValueError("table_id required for bika.create_record")
    payload = merged
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/tables/{table_id}/records", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("bika.create_record")
    return {"data": data}
