"""Weekdone team management (alias) — handler for weekdone integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.weekdone.com/2"


@register_node("weekdone.list_teams")
async def weekdone_list_teams(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List teams.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/teams", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("weekdone.list_teams")
    return {"data": data}

@register_node("weekdone.list_users")
async def weekdone_list_users(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List users.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/users", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("weekdone.list_users")
    return {"data": data}

@register_node("weekdone.create_item")
async def weekdone_create_item(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a progress item.

    config/input_data:
      api_key — API key or token (required)
      text — (required)
      type — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    text = merged.get("text") or ""
    type = merged.get("type") or ""
    if not text or not type:
        raise ValueError("text, type required for weekdone.create_item")
    payload = {"text": text, "type": type}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/items", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("weekdone.create_item")
    return {"data": data}
