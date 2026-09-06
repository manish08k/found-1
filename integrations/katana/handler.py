"""Katana integration — manufacturing and inventory management."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://app.katanamrp.com/api/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("katana.get_products")
async def katana_get_products(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/products", params={"limit": merged.get("limit", 20)})
        r.raise_for_status()
    return {"products": r.json()}


@register_node("katana.create_sales_order")
async def katana_create_sales_order(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/sales_orders", json={
            "customer_id": merged.get("customer_id", ""),
            "order_no": merged.get("order_no", ""),
            "order_row": merged.get("items", []),
        })
        r.raise_for_status()
    return r.json()


@register_node("katana.get_inventory")
async def katana_get_inventory(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/inventories")
        r.raise_for_status()
    return {"inventory": r.json()}
