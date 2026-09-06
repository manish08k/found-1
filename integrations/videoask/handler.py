"""VideoAsk interactive video conversations — handler for videoask integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.videoask.com/v1"


@register_node("videoask.list_videoasks")
async def videoask_list_videoasks(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List VideoAsks.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/videoasks", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("videoask.list_videoasks")
    return {"data": data}

@register_node("videoask.get_videoask")
async def videoask_get_videoask(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get VideoAsk details.

    config/input_data:
      api_key — API key or token (required)
      videoask_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    videoask_id = merged.get("videoask_id") or ""
    if not videoask_id:
        raise ValueError("videoask_id required for videoask.get_videoask")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/videoasks/{videoask_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("videoask.get_videoask")
    return {"data": data}

@register_node("videoask.list_contacts")
async def videoask_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/contacts", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("videoask.list_contacts")
    return {"data": data}
