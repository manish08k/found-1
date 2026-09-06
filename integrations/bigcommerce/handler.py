"""BigCommerce integration — products, orders, and customers."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _bc_base(store_hash: str) -> str:
    return f"https://api.bigcommerce.com/stores/{store_hash}/v2"


def _bc_headers(access_token: str) -> dict:
    return {
        "X-Auth-Token": access_token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


@register_node("bigcommerce.list_products")
async def bigcommerce_list_products(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List products in a BigCommerce store.

    config:
      store_hash   — BigCommerce store hash (required)
      access_token — BigCommerce API access token (required)
      limit        — number of products to return (optional, default 50)
      page         — page number (optional, default 1)
    """
    merged = {**config, **input_data}
    store_hash = merged.get("store_hash", "")
    access_token = merged.get("access_token", "")
    if not store_hash or not access_token:
        raise ValueError("store_hash and access_token are required for bigcommerce.list_products")

    params = {"limit": merged.get("limit", 50), "page": merged.get("page", 1)}

    async with httpx.AsyncClient(base_url=_bc_base(store_hash), timeout=30) as client:
        r = await client.get("/products", headers=_bc_headers(access_token), params=params)
        r.raise_for_status()
        products = r.json()

    log.info("bigcommerce.list_products", store_hash=store_hash, count=len(products))
    return {"products": products, "count": len(products)}


@register_node("bigcommerce.get_product")
async def bigcommerce_get_product(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single BigCommerce product by ID.

    config:
      store_hash   — BigCommerce store hash (required)
      access_token — BigCommerce API access token (required)
      product_id   — product ID to retrieve (required)
    """
    merged = {**config, **input_data}
    store_hash = merged.get("store_hash", "")
    access_token = merged.get("access_token", "")
    product_id = merged.get("product_id")
    if not store_hash or not access_token or not product_id:
        raise ValueError("store_hash, access_token, and product_id are required")

    async with httpx.AsyncClient(base_url=_bc_base(store_hash), timeout=30) as client:
        r = await client.get(f"/products/{product_id}", headers=_bc_headers(access_token))
        r.raise_for_status()
        product = r.json()

    log.info("bigcommerce.get_product", product_id=product_id)
    return {"product": product, "product_id": product_id}


@register_node("bigcommerce.create_product")
async def bigcommerce_create_product(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new product in a BigCommerce store.

    config:
      store_hash   — BigCommerce store hash (required)
      access_token — BigCommerce API access token (required)
      name         — product name (required)
      type         — product type: physical/digital (required)
      price        — product price (required)
      weight       — product weight (required for physical)
      sku          — product SKU (optional)
    """
    merged = {**config, **input_data}
    store_hash = merged.get("store_hash", "")
    access_token = merged.get("access_token", "")
    if not store_hash or not access_token:
        raise ValueError("store_hash and access_token are required")

    payload = {k: v for k, v in {
        "name": merged.get("name"),
        "type": merged.get("type", "physical"),
        "price": merged.get("price"),
        "weight": merged.get("weight", 0),
        "sku": merged.get("sku"),
        "description": merged.get("description"),
        "inventory_tracking": merged.get("inventory_tracking"),
    }.items() if v is not None}

    async with httpx.AsyncClient(base_url=_bc_base(store_hash), timeout=30) as client:
        r = await client.post("/products", headers=_bc_headers(access_token), json=payload)
        r.raise_for_status()
        product = r.json()

    product_id = product.get("id")
    log.info("bigcommerce.create_product", product_id=product_id)
    return {"product": product, "product_id": product_id}


@register_node("bigcommerce.list_orders")
async def bigcommerce_list_orders(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List orders in a BigCommerce store.

    config:
      store_hash   — BigCommerce store hash (required)
      access_token — BigCommerce API access token (required)
      limit        — number of orders to return (optional, default 50)
      page         — page number (optional, default 1)
      status_id    — filter by order status ID (optional)
    """
    merged = {**config, **input_data}
    store_hash = merged.get("store_hash", "")
    access_token = merged.get("access_token", "")
    if not store_hash or not access_token:
        raise ValueError("store_hash and access_token are required")

    params: dict = {"limit": merged.get("limit", 50), "page": merged.get("page", 1)}
    if merged.get("status_id") is not None:
        params["status_id"] = merged["status_id"]

    async with httpx.AsyncClient(base_url=_bc_base(store_hash), timeout=30) as client:
        r = await client.get("/orders", headers=_bc_headers(access_token), params=params)
        r.raise_for_status()
        orders = r.json()

    log.info("bigcommerce.list_orders", store_hash=store_hash, count=len(orders))
    return {"orders": orders, "count": len(orders)}


@register_node("bigcommerce.get_order")
async def bigcommerce_get_order(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single BigCommerce order by ID.

    config:
      store_hash   — BigCommerce store hash (required)
      access_token — BigCommerce API access token (required)
      order_id     — order ID to retrieve (required)
    """
    merged = {**config, **input_data}
    store_hash = merged.get("store_hash", "")
    access_token = merged.get("access_token", "")
    order_id = merged.get("order_id")
    if not store_hash or not access_token or not order_id:
        raise ValueError("store_hash, access_token, and order_id are required")

    async with httpx.AsyncClient(base_url=_bc_base(store_hash), timeout=30) as client:
        r = await client.get(f"/orders/{order_id}", headers=_bc_headers(access_token))
        r.raise_for_status()
        order = r.json()

    log.info("bigcommerce.get_order", order_id=order_id)
    return {"order": order, "order_id": order_id}


@register_node("bigcommerce.list_customers")
async def bigcommerce_list_customers(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List customers in a BigCommerce store.

    config:
      store_hash   — BigCommerce store hash (required)
      access_token — BigCommerce API access token (required)
      limit        — number of customers to return (optional, default 50)
      page         — page number (optional, default 1)
    """
    merged = {**config, **input_data}
    store_hash = merged.get("store_hash", "")
    access_token = merged.get("access_token", "")
    if not store_hash or not access_token:
        raise ValueError("store_hash and access_token are required")

    params = {"limit": merged.get("limit", 50), "page": merged.get("page", 1)}

    async with httpx.AsyncClient(base_url=_bc_base(store_hash), timeout=30) as client:
        r = await client.get("/customers", headers=_bc_headers(access_token), params=params)
        r.raise_for_status()
        customers = r.json()

    log.info("bigcommerce.list_customers", store_hash=store_hash, count=len(customers))
    return {"customers": customers, "count": len(customers)}
