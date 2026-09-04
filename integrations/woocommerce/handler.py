"""
WooCommerce ecommerce integration.

WooCommerce REST API v3 uses HTTP Basic Auth (consumer_key:consumer_secret).
Reference: https://woocommerce.github.io/woocommerce-rest-api-docs/

Credential fields (stored as api-key credential):
  - store_url:       https://yourstore.com  (no trailing slash)
  - consumer_key:    ck_xxxx
  - consumer_secret: cs_xxxx
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

WC_API_VERSION = "wc/v3"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    store_url = creds.get("store_url", "").rstrip("/")
    consumer_key = creds.get("consumer_key")
    consumer_secret = creds.get("consumer_secret")
    if not store_url:
        raise ValueError("WooCommerce credential missing 'store_url'")
    if not consumer_key or not consumer_secret:
        raise ValueError("WooCommerce credential missing 'consumer_key' or 'consumer_secret'")
    return httpx.AsyncClient(
        base_url=f"{store_url}/{WC_API_VERSION}",
        auth=(consumer_key, consumer_secret),
        headers={"Content-Type": "application/json"},
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict | list:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"WooCommerce API error {r.status_code}: {detail}")
    return r.json()


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

@register_node("woocommerce.get_order")
async def woocommerce_get_order(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /orders/{id} — fetch a single order by ID."""
    order_id = config.get("order_id") or input_data.get("order_id")
    if not order_id:
        raise ValueError("woocommerce.get_order requires 'order_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/orders/{order_id}")
    return {"order": _check(r)}


@register_node("woocommerce.list_orders")
async def woocommerce_list_orders(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /orders — list orders with optional filters."""
    params: dict = {}
    for key in ("status", "customer", "product", "per_page", "page", "after", "before", "search"):
        val = config.get(key) or input_data.get(key)
        if val is not None:
            params[key] = val
    if "per_page" in params:
        params["per_page"] = min(int(params["per_page"]), 100)
    async with await _client(credential_id, db) as client:
        r = await client.get("/orders", params=params)
    return {"orders": _check(r)}


@register_node("woocommerce.update_order")
async def woocommerce_update_order(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /orders/{id} — update an order (status, note, etc.)."""
    order_id = config.get("order_id") or input_data.get("order_id")
    if not order_id:
        raise ValueError("woocommerce.update_order requires 'order_id'")
    payload: dict = {}
    for key in ("status", "customer_note", "billing", "shipping"):
        val = config.get(key) or input_data.get(key)
        if val is not None:
            payload[key] = val
    async with await _client(credential_id, db) as client:
        r = await client.put(f"/orders/{order_id}", json=payload)
    return {"order": _check(r)}


@register_node("woocommerce.create_order")
async def woocommerce_create_order(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /orders — create a new order."""
    payload = config.get("order") or input_data.get("order")
    if not payload or not isinstance(payload, dict):
        raise ValueError("woocommerce.create_order requires 'order' dict")
    async with await _client(credential_id, db) as client:
        r = await client.post("/orders", json=payload)
    return {"order": _check(r)}


@register_node("woocommerce.delete_order")
async def woocommerce_delete_order(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /orders/{id} — delete/trash an order."""
    order_id = config.get("order_id") or input_data.get("order_id")
    if not order_id:
        raise ValueError("woocommerce.delete_order requires 'order_id'")
    force = config.get("force", False)
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/orders/{order_id}", params={"force": str(force).lower()})
    return {"deleted": _check(r)}


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

@register_node("woocommerce.get_product")
async def woocommerce_get_product(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /products/{id} — fetch a single product."""
    product_id = config.get("product_id") or input_data.get("product_id")
    if not product_id:
        raise ValueError("woocommerce.get_product requires 'product_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/products/{product_id}")
    return {"product": _check(r)}


@register_node("woocommerce.list_products")
async def woocommerce_list_products(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /products — list products with optional filters."""
    params: dict = {}
    for key in ("status", "category", "tag", "type", "search", "per_page", "page", "sku"):
        val = config.get(key) or input_data.get(key)
        if val is not None:
            params[key] = val
    if "per_page" in params:
        params["per_page"] = min(int(params["per_page"]), 100)
    async with await _client(credential_id, db) as client:
        r = await client.get("/products", params=params)
    return {"products": _check(r)}


@register_node("woocommerce.create_product")
async def woocommerce_create_product(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /products — create a new product."""
    payload = config.get("product") or input_data.get("product")
    if not payload or not isinstance(payload, dict):
        raise ValueError("woocommerce.create_product requires 'product' dict")
    async with await _client(credential_id, db) as client:
        r = await client.post("/products", json=payload)
    return {"product": _check(r)}


@register_node("woocommerce.update_product")
async def woocommerce_update_product(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /products/{id} — update a product."""
    product_id = config.get("product_id") or input_data.get("product_id")
    if not product_id:
        raise ValueError("woocommerce.update_product requires 'product_id'")
    payload: dict = {}
    for key in ("name", "status", "description", "regular_price", "sale_price",
                "stock_quantity", "manage_stock", "categories", "tags", "images"):
        val = config.get(key) if config.get(key) is not None else input_data.get(key)
        if val is not None:
            payload[key] = val
    async with await _client(credential_id, db) as client:
        r = await client.put(f"/products/{product_id}", json=payload)
    return {"product": _check(r)}


@register_node("woocommerce.delete_product")
async def woocommerce_delete_product(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /products/{id} — delete/trash a product."""
    product_id = config.get("product_id") or input_data.get("product_id")
    if not product_id:
        raise ValueError("woocommerce.delete_product requires 'product_id'")
    force = config.get("force", False)
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/products/{product_id}", params={"force": str(force).lower()})
    return {"deleted": _check(r)}


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------

@register_node("woocommerce.get_customer")
async def woocommerce_get_customer(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /customers/{id} — fetch a single customer."""
    customer_id = config.get("customer_id") or input_data.get("customer_id")
    if not customer_id:
        raise ValueError("woocommerce.get_customer requires 'customer_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/customers/{customer_id}")
    return {"customer": _check(r)}


@register_node("woocommerce.list_customers")
async def woocommerce_list_customers(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /customers — list customers."""
    params: dict = {}
    for key in ("search", "email", "role", "per_page", "page", "order", "orderby"):
        val = config.get(key) or input_data.get(key)
        if val is not None:
            params[key] = val
    if "per_page" in params:
        params["per_page"] = min(int(params["per_page"]), 100)
    async with await _client(credential_id, db) as client:
        r = await client.get("/customers", params=params)
    return {"customers": _check(r)}


@register_node("woocommerce.create_customer")
async def woocommerce_create_customer(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /customers — create a new customer."""
    payload: dict = {}
    for key in ("email", "first_name", "last_name", "username", "password",
                "billing", "shipping", "meta_data"):
        val = config.get(key) if config.get(key) is not None else input_data.get(key)
        if val is not None:
            payload[key] = val
    if not payload.get("email"):
        raise ValueError("woocommerce.create_customer requires 'email'")
    async with await _client(credential_id, db) as client:
        r = await client.post("/customers", json=payload)
    return {"customer": _check(r)}


@register_node("woocommerce.update_customer")
async def woocommerce_update_customer(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /customers/{id} — update customer details."""
    customer_id = config.get("customer_id") or input_data.get("customer_id")
    if not customer_id:
        raise ValueError("woocommerce.update_customer requires 'customer_id'")
    payload: dict = {}
    for key in ("email", "first_name", "last_name", "billing", "shipping", "meta_data"):
        val = config.get(key) if config.get(key) is not None else input_data.get(key)
        if val is not None:
            payload[key] = val
    async with await _client(credential_id, db) as client:
        r = await client.put(f"/customers/{customer_id}", json=payload)
    return {"customer": _check(r)}


# ---------------------------------------------------------------------------
# Coupons
# ---------------------------------------------------------------------------

@register_node("woocommerce.list_coupons")
async def woocommerce_list_coupons(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /coupons — list coupons."""
    params: dict = {}
    for key in ("search", "code", "per_page", "page"):
        val = config.get(key) or input_data.get(key)
        if val is not None:
            params[key] = val
    async with await _client(credential_id, db) as client:
        r = await client.get("/coupons", params=params)
    return {"coupons": _check(r)}


@register_node("woocommerce.create_coupon")
async def woocommerce_create_coupon(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /coupons — create a new coupon."""
    payload: dict = {}
    for key in ("code", "discount_type", "amount", "individual_use",
                "usage_limit", "expiry_date", "product_ids", "excluded_product_ids"):
        val = config.get(key) if config.get(key) is not None else input_data.get(key)
        if val is not None:
            payload[key] = val
    if not payload.get("code"):
        raise ValueError("woocommerce.create_coupon requires 'code'")
    async with await _client(credential_id, db) as client:
        r = await client.post("/coupons", json=payload)
    return {"coupon": _check(r)}


# ---------------------------------------------------------------------------
# Reports / System Status
# ---------------------------------------------------------------------------

@register_node("woocommerce.get_sales_report")
async def woocommerce_get_sales_report(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /reports/sales — get sales totals."""
    params: dict = {}
    for key in ("date_min", "date_max", "period"):
        val = config.get(key) or input_data.get(key)
        if val is not None:
            params[key] = val
    async with await _client(credential_id, db) as client:
        r = await client.get("/reports/sales", params=params)
    return {"report": _check(r)}


@register_node("woocommerce.get_system_status")
async def woocommerce_get_system_status(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /system_status — retrieve store system status info."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/system_status")
    return {"system_status": _check(r)}


# ---------------------------------------------------------------------------
# Connection test (called by the credential validation endpoint)
# ---------------------------------------------------------------------------

async def test_connection(creds: dict) -> None:
    """Verify WooCommerce credentials by fetching a single product page."""
    store_url = creds.get("store_url", "").rstrip("/")
    consumer_key = creds.get("consumer_key")
    consumer_secret = creds.get("consumer_secret")
    if not store_url or not consumer_key or not consumer_secret:
        raise ValueError("WooCommerce requires store_url, consumer_key, and consumer_secret")
    async with httpx.AsyncClient(
        base_url=f"{store_url}/{WC_API_VERSION}",
        auth=(consumer_key, consumer_secret),
        timeout=15.0,
    ) as client:
        r = await client.get("/products", params={"per_page": 1})
    if not r.is_success:
        raise ValueError(f"WooCommerce connection failed: {r.status_code} {r.text[:200]}")
