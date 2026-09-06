"""Base44 no-code backend platform — handler for base44 integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.base44.com/v1"


@register_node("base44.list_entities")
async def base44_list_entities(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all entities.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/entities", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("base44.list_entities")
    return {"data": data}

@register_node("base44.create_record")
async def base44_create_record(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a record.

    config/input_data:
      api_key — API key or token (required)
      entity — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    entity = merged.get("entity") or ""
    if not entity:
        raise ValueError("entity required for base44.create_record")
    payload = merged
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/entities/{entity}/records", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("base44.create_record")
    return {"data": data}

@register_node("base44.list_records")
async def base44_list_records(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List records.

    config/input_data:
      api_key — API key or token (required)
      entity — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    entity = merged.get("entity") or ""
    if not entity:
        raise ValueError("entity required for base44.list_records")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/entities/{entity}/records", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("base44.list_records")
    return {"data": data}
