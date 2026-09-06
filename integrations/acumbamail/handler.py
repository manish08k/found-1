"""Acumbamail email marketing platform — handler for acumbamail integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://acumbamail.com/api/1"


@register_node("acumbamail.list_subscriber_lists")
async def acumbamail_list_subscriber_lists(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List subscriber lists.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Content-Type": "application/json"}
    # Auth passed as query param: auth_token
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/getLists/", headers=headers, params={"auth_token": api_key})
        r.raise_for_status()
        data = r.json()
    log.info("acumbamail.list_subscriber_lists")
    return {"data": data}

@register_node("acumbamail.add_subscriber")
async def acumbamail_add_subscriber(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Add a subscriber to a list.

    config/input_data:
      api_key — API key or token (required)
      list_id — (required)
      email — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Content-Type": "application/json"}
    # Auth passed as query param: auth_token
    list_id = merged.get("list_id") or ""
    email = merged.get("email") or ""
    if not list_id or not email:
        raise ValueError("list_id, email required for acumbamail.add_subscriber")
    payload = {"list_id": list_id, "email": email}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/addSubscriber/", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("acumbamail.add_subscriber")
    return {"data": data}

@register_node("acumbamail.delete_subscriber")
async def acumbamail_delete_subscriber(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Remove subscriber from a list.

    config/input_data:
      api_key — API key or token (required)
      list_id — (required)
      email — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Content-Type": "application/json"}
    # Auth passed as query param: auth_token
    list_id = merged.get("list_id") or ""
    email = merged.get("email") or ""
    if not list_id or not email:
        raise ValueError("list_id, email required for acumbamail.delete_subscriber")
    payload = {"list_id": list_id, "email": email}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/deleteSubscriber/", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("acumbamail.delete_subscriber")
    return {"data": data}
