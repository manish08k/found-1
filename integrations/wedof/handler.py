"""Wedof French training organization management — handler for wedof integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.wedof.fr/v1"


@register_node("wedof.list_registrations")
async def wedof_list_registrations(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List registration folders.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/registrationFolders", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("wedof.list_registrations")
    return {"data": data}

@register_node("wedof.get_registration")
async def wedof_get_registration(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get registration details.

    config/input_data:
      api_key — API key or token (required)
      id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    id = merged.get("id") or ""
    if not id:
        raise ValueError("id required for wedof.get_registration")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/registrationFolders/{id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("wedof.get_registration")
    return {"data": data}
