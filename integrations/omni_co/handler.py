"""Omni.co unified commerce platform — handler for omni_co integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.omni.co/v1"


@register_node("omni_co.list_orders")
async def omni_co_list_orders(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List orders.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/orders", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("omni_co.list_orders")
    return {"data": data}

@register_node("omni_co.get_order")
async def omni_co_get_order(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get order details.

    config/input_data:
      api_key — API key or token (required)
      order_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    order_id = merged.get("order_id") or ""
    if not order_id:
        raise ValueError("order_id required for omni_co.get_order")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/orders/{order_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("omni_co.get_order")
    return {"data": data}

@register_node("omni_co.list_products")
async def omni_co_list_products(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
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
    log.info("omni_co.list_products")
    return {"data": data}
