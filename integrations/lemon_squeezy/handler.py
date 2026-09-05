"""Lemon Squeezy integration — stores, products, orders, and subscriptions."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

LS_BASE = "https://api.lemonsqueezy.com/v1"


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Accept": "application/vnd.api+json"}


@register_node("lemon_squeezy.list_stores")
async def ls_list_stores(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Lemon Squeezy stores for the authenticated account.

    config:
      api_key — Lemon Squeezy API key (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for lemon_squeezy.list_stores")

    async with httpx.AsyncClient(base_url=LS_BASE, timeout=30) as client:
        r = await client.get("/stores", headers=_headers(api_key))
        r.raise_for_status()
        data = r.json()

    stores = data.get("data", [])
    log.info("lemon_squeezy.list_stores", count=len(stores))
    return {"stores": stores, "count": len(stores), "meta": data.get("meta", {})}


@register_node("lemon_squeezy.list_products")
async def ls_list_products(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List products filtered by store.

    config:
      api_key  — Lemon Squeezy API key (required)
      store_id — Store ID to filter by (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    store_id = config.get("store_id") or input_data.get("store_id")
    if not api_key:
        raise ValueError("api_key is required for lemon_squeezy.list_products")
    if not store_id:
        raise ValueError("store_id is required for lemon_squeezy.list_products")

    async with httpx.AsyncClient(base_url=LS_BASE, timeout=30) as client:
        r = await client.get(
            "/products",
            headers=_headers(api_key),
            params={"filter[store_id]": store_id},
        )
        r.raise_for_status()
        data = r.json()

    products = data.get("data", [])
    log.info("lemon_squeezy.list_products", store_id=store_id, count=len(products))
    return {"products": products, "count": len(products), "meta": data.get("meta", {})}


@register_node("lemon_squeezy.list_orders")
async def ls_list_orders(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List orders filtered by store.

    config:
      api_key  — Lemon Squeezy API key (required)
      store_id — Store ID to filter by (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    store_id = config.get("store_id") or input_data.get("store_id")
    if not api_key:
        raise ValueError("api_key is required for lemon_squeezy.list_orders")
    if not store_id:
        raise ValueError("store_id is required for lemon_squeezy.list_orders")

    async with httpx.AsyncClient(base_url=LS_BASE, timeout=30) as client:
        r = await client.get(
            "/orders",
            headers=_headers(api_key),
            params={"filter[store_id]": store_id},
        )
        r.raise_for_status()
        data = r.json()

    orders = data.get("data", [])
    log.info("lemon_squeezy.list_orders", store_id=store_id, count=len(orders))
    return {"orders": orders, "count": len(orders), "meta": data.get("meta", {})}


@register_node("lemon_squeezy.list_subscriptions")
async def ls_list_subscriptions(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all subscriptions.

    config:
      api_key — Lemon Squeezy API key (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for lemon_squeezy.list_subscriptions")

    async with httpx.AsyncClient(base_url=LS_BASE, timeout=30) as client:
        r = await client.get("/subscriptions", headers=_headers(api_key))
        r.raise_for_status()
        data = r.json()

    subscriptions = data.get("data", [])
    log.info("lemon_squeezy.list_subscriptions", count=len(subscriptions))
    return {"subscriptions": subscriptions, "count": len(subscriptions), "meta": data.get("meta", {})}


@register_node("lemon_squeezy.get_subscription")
async def ls_get_subscription(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single subscription by ID.

    config:
      api_key — Lemon Squeezy API key (required)
      id      — Subscription ID (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    subscription_id = config.get("id") or input_data.get("id")
    if not api_key:
        raise ValueError("api_key is required for lemon_squeezy.get_subscription")
    if not subscription_id:
        raise ValueError("id is required for lemon_squeezy.get_subscription")

    async with httpx.AsyncClient(base_url=LS_BASE, timeout=30) as client:
        r = await client.get(f"/subscriptions/{subscription_id}", headers=_headers(api_key))
        r.raise_for_status()
        data = r.json()

    subscription = data.get("data", {})
    log.info("lemon_squeezy.get_subscription", subscription_id=subscription_id)
    return {"subscription": subscription, "id": subscription_id}
