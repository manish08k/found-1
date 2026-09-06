"""Uscreen video membership platform — handler for uscreen integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.uscreen.tv/v1"


@register_node("uscreen.list_customers")
async def uscreen_list_customers(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List customers.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/customers", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("uscreen.list_customers")
    return {"data": data}

@register_node("uscreen.get_customer")
async def uscreen_get_customer(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get customer details.

    config/input_data:
      api_key — API key or token (required)
      customer_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    customer_id = merged.get("customer_id") or ""
    if not customer_id:
        raise ValueError("customer_id required for uscreen.get_customer")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/customers/{customer_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("uscreen.get_customer")
    return {"data": data}

@register_node("uscreen.list_products")
async def uscreen_list_products(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List products.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/products", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("uscreen.list_products")
    return {"data": data}
