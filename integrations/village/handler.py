"""Village cloud compute management — handler for village integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.village.dev/v1"


@register_node("village.list_instances")
async def village_list_instances(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List compute instances.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/instances", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("village.list_instances")
    return {"data": data}

@register_node("village.create_instance")
async def village_create_instance(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a compute instance.

    config/input_data:
      api_key — API key or token (required)
      type — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    type = merged.get("type") or ""
    if not type:
        raise ValueError("type required for village.create_instance")
    payload = {"type": type}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/instances", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("village.create_instance")
    return {"data": data}

@register_node("village.delete_instance")
async def village_delete_instance(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete an instance.

    config/input_data:
      api_key — API key or token (required)
      instance_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    instance_id = merged.get("instance_id") or ""
    if not instance_id:
        raise ValueError("instance_id required for village.delete_instance")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.delete(f"{BASE_URL}/instances/{instance_id}", headers=headers)
        r.raise_for_status()
    log.info("village.delete_instance")
    return {"ok": True}
