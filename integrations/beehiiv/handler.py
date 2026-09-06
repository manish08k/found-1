"""beehiiv newsletter platform (Activepieces naming variant) — handler for beehiiv integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.beehiiv.com/v2"


@register_node("beehiiv.list_publications")
async def beehiiv_list_publications(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List publications.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/publications", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("beehiiv.list_publications")
    return {"data": data}

@register_node("beehiiv.list_subscribers")
async def beehiiv_list_subscribers(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List subscribers.

    config/input_data:
      api_key — API key or token (required)
      pub_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    pub_id = merged.get("pub_id") or ""
    if not pub_id:
        raise ValueError("pub_id required for beehiiv.list_subscribers")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/publications/{pub_id}/subscriptions", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("beehiiv.list_subscribers")
    return {"data": data}

@register_node("beehiiv.create_subscriber")
async def beehiiv_create_subscriber(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create subscriber.

    config/input_data:
      api_key — API key or token (required)
      pub_id — (required)
      email — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    pub_id = merged.get("pub_id") or ""
    email = merged.get("email") or ""
    if not pub_id or not email:
        raise ValueError("pub_id, email required for beehiiv.create_subscriber")
    payload = {"email": email}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/publications/{pub_id}/subscriptions", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("beehiiv.create_subscriber")
    return {"data": data}
