"""Cartloom e-commerce platform — handler for cartloom integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.cartloom.com/v1"


@register_node("cartloom.list_products")
async def cartloom_list_products(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
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
    log.info("cartloom.list_products")
    return {"data": data}

@register_node("cartloom.create_product")
async def cartloom_create_product(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a product.

    config/input_data:
      api_key — API key or token (required)
      name — (required)
      price — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    name = merged.get("name") or ""
    price = merged.get("price") or ""
    if not name or not price:
        raise ValueError("name, price required for cartloom.create_product")
    payload = {"name": name, "price": price}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/products", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("cartloom.create_product")
    return {"data": data}

@register_node("cartloom.list_orders")
async def cartloom_list_orders(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
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
    log.info("cartloom.list_orders")
    return {"data": data}
