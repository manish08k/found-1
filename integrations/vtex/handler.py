"""VTEX e-commerce platform — handler for vtex integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL_TEMPLATE = "https://{account_name}.vtexcommercestable.com.br/api"


def _build_base_url(merged: dict) -> str:
    account_name = merged.get("account_name") or merged.get("subdomain") or ""
    if not account_name:
        raise ValueError("account_name (subdomain) is required for vtex operations")
    return BASE_URL_TEMPLATE.format(account_name=account_name)


def _build_headers(merged: dict) -> dict:
    api_key = merged.get("api_key") or merged.get("app_key") or ""
    api_token = merged.get("api_token") or merged.get("app_token") or ""
    return {
        "X-VTEX-API-AppKey": api_key,
        "X-VTEX-API-AppToken": api_token,
        "Content-Type": "application/json",
    }


@register_node("vtex.list_orders")
async def vtex_list_orders(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List orders.

    config/input_data:
      account_name / subdomain — VTEX account name (required)
      api_key / app_key — (required)
      api_token / app_token — (required)
    """
    merged = {**config, **input_data}
    base_url = _build_base_url(merged)
    headers = _build_headers(merged)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base_url}/oms/pvt/orders", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("vtex.list_orders")
    return {"data": data}

@register_node("vtex.get_order")
async def vtex_get_order(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get order details.

    config/input_data:
      account_name / subdomain — VTEX account name (required)
      api_key / app_key — (required)
      api_token / app_token — (required)
      order_id — (required)
    """
    merged = {**config, **input_data}
    base_url = _build_base_url(merged)
    headers = _build_headers(merged)
    order_id = merged.get("order_id") or ""
    if not order_id:
        raise ValueError("order_id required for vtex.get_order")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base_url}/oms/pvt/orders/{order_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("vtex.get_order")
    return {"data": data}

@register_node("vtex.list_products")
async def vtex_list_products(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List products.

    config/input_data:
      account_name / subdomain — VTEX account name (required)
      api_key / app_key — (required)
      api_token / app_token — (required)
    """
    merged = {**config, **input_data}
    base_url = _build_base_url(merged)
    headers = _build_headers(merged)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base_url}/catalog_system/pvt/products/GetProductAndSkuIds", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("vtex.list_products")
    return {"data": data}
