"""Weekdone OKR and goal tracking — handler for week_done integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.weekdone.com/2"


@register_node("week_done.list_objectives")
async def week_done_list_objectives(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List objectives.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/objectives", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("week_done.list_objectives")
    return {"data": data}

@register_node("week_done.create_objective")
async def week_done_create_objective(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create an objective.

    config/input_data:
      api_key — API key or token (required)
      name — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    name = merged.get("name") or ""
    if not name:
        raise ValueError("name required for week_done.create_objective")
    payload = {"name": name}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/objectives", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("week_done.create_objective")
    return {"data": data}

@register_node("week_done.list_updates")
async def week_done_list_updates(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List weekly updates.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/updates", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("week_done.list_updates")
    return {"data": data}
