"""
Shopify ecommerce integration.

Credential fields:
  - shop_domain: yourshop.myshopify.com
  - access_token: Shopify Admin API access token

Auth: X-Shopify-Access-Token header
Base URL: https://{shop_domain}/admin/api/2024-01
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

SHOPIFY_API_VERSION = "2024-01"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    shop_domain = creds.get("shop_domain")
    access_token = creds.get("access_token")
    if not shop_domain:
        raise ValueError("Shopify credential is missing 'shop_domain'")
    if not access_token:
        raise ValueError("Shopify credential is missing 'access_token'")
    base_url = f"https://{shop_domain}/admin/api/{SHOPIFY_API_VERSION}"
    return httpx.AsyncClient(
        base_url=base_url,
        headers={
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Shopify API error {r.status_code}: {detail}")
    return r.json()


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

@register_node("shopify.get_order")
async def shopify_get_order(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /orders/{id}.json — fetch a single order by ID."""
    order_id = config.get("order_id") or input_data.get("order_id")
    if not order_id:
        raise ValueError("shopify.get_order requires 'order_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/orders/{order_id}.json")
    return _check(r)


@register_node("shopify.list_orders")
async def shopify_list_orders(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /orders.json — list orders with optional filters."""
    params = {}
    status = config.get("status") or input_data.get("status")
    if status:
        params["status"] = status
    limit = config.get("limit") or input_data.get("limit")
    if limit:
        params["limit"] = min(int(limit), 250)
    since_id = config.get("since_id") or input_data.get("since_id")
    if since_id:
        params["since_id"] = since_id
    financial_status = config.get("financial_status") or input_data.get("financial_status")
    if financial_status:
        params["financial_status"] = financial_status
    fulfillment_status = config.get("fulfillment_status") or input_data.get("fulfillment_status")
    if fulfillment_status:
        params["fulfillment_status"] = fulfillment_status
    async with await _client(credential_id, db) as client:
        r = await client.get("/orders.json", params=params)
    return _check(r)


@register_node("shopify.create_order")
async def shopify_create_order(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /orders.json — create a new order."""
    line_items = config.get("line_items") or input_data.get("line_items")
    if not line_items:
        raise ValueError("shopify.create_order requires 'line_items'")
    body: dict = {"order": {"line_items": line_items}}
    customer = config.get("customer") or input_data.get("customer")
    if customer:
        body["order"]["customer"] = customer
    shipping_address = config.get("shipping_address") or input_data.get("shipping_address")
    if shipping_address:
        body["order"]["shipping_address"] = shipping_address
    async with await _client(credential_id, db) as client:
        r = await client.post("/orders.json", json=body)
    return _check(r)


@register_node("shopify.update_order")
async def shopify_update_order(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /orders/{id}.json — update an existing order."""
    order_id = config.get("order_id") or input_data.get("order_id")
    if not order_id:
        raise ValueError("shopify.update_order requires 'order_id'")
    order_body: dict = {}
    for field in ("note", "tags", "email"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            order_body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.put(f"/orders/{order_id}.json", json={"order": order_body})
    return _check(r)


@register_node("shopify.cancel_order")
async def shopify_cancel_order(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /orders/{id}/cancel.json — cancel an order."""
    order_id = config.get("order_id") or input_data.get("order_id")
    if not order_id:
        raise ValueError("shopify.cancel_order requires 'order_id'")
    body: dict = {}
    reason = config.get("reason") or input_data.get("reason")
    if reason:
        body["reason"] = reason
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/orders/{order_id}/cancel.json", json=body)
    return _check(r)


@register_node("shopify.fulfill_order")
async def shopify_fulfill_order(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /orders/{id}/fulfillments.json — create a fulfillment for an order."""
    order_id = config.get("order_id") or input_data.get("order_id")
    if not order_id:
        raise ValueError("shopify.fulfill_order requires 'order_id'")
    fulfillment: dict = {}
    tracking_number = config.get("tracking_number") or input_data.get("tracking_number")
    if tracking_number:
        fulfillment["tracking_number"] = tracking_number
    tracking_company = config.get("tracking_company") or input_data.get("tracking_company")
    if tracking_company:
        fulfillment["tracking_company"] = tracking_company
    notify_customer = config.get("notify_customer")
    if notify_customer is None:
        notify_customer = input_data.get("notify_customer")
    if notify_customer is not None:
        fulfillment["notify_customer"] = bool(notify_customer)
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/orders/{order_id}/fulfillments.json", json={"fulfillment": fulfillment})
    return _check(r)


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

@register_node("shopify.get_product")
async def shopify_get_product(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /products/{id}.json — fetch a single product."""
    product_id = config.get("product_id") or input_data.get("product_id")
    if not product_id:
        raise ValueError("shopify.get_product requires 'product_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/products/{product_id}.json")
    return _check(r)


@register_node("shopify.list_products")
async def shopify_list_products(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /products.json — list products."""
    params = {}
    limit = config.get("limit") or input_data.get("limit")
    if limit:
        params["limit"] = min(int(limit), 250)
    status = config.get("status") or input_data.get("status")
    if status:
        params["status"] = status
    vendor = config.get("vendor") or input_data.get("vendor")
    if vendor:
        params["vendor"] = vendor
    product_type = config.get("product_type") or input_data.get("product_type")
    if product_type:
        params["product_type"] = product_type
    async with await _client(credential_id, db) as client:
        r = await client.get("/products.json", params=params)
    return _check(r)


@register_node("shopify.create_product")
async def shopify_create_product(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /products.json — create a new product."""
    title = config.get("title") or input_data.get("title")
    if not title:
        raise ValueError("shopify.create_product requires 'title'")
    product: dict = {"title": title}
    for field in ("body_html", "vendor", "product_type", "status"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            product[field] = v
    variants = config.get("variants") or input_data.get("variants")
    if variants:
        product["variants"] = variants
    async with await _client(credential_id, db) as client:
        r = await client.post("/products.json", json={"product": product})
    return _check(r)


@register_node("shopify.update_product")
async def shopify_update_product(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /products/{id}.json — update a product."""
    product_id = config.get("product_id") or input_data.get("product_id")
    if not product_id:
        raise ValueError("shopify.update_product requires 'product_id'")
    product: dict = {}
    for field in ("title", "body_html", "vendor", "product_type", "status", "variants"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            product[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.put(f"/products/{product_id}.json", json={"product": product})
    return _check(r)


@register_node("shopify.update_inventory")
async def shopify_update_inventory(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /inventory_levels/set.json — set inventory level for a variant at a location."""
    location_id = config.get("location_id") or input_data.get("location_id")
    inventory_item_id = config.get("inventory_item_id") or input_data.get("inventory_item_id")
    available = config.get("available")
    if available is None:
        available = input_data.get("available")
    if not location_id or not inventory_item_id or available is None:
        raise ValueError("shopify.update_inventory requires 'location_id', 'inventory_item_id', and 'available'")
    body = {
        "location_id": location_id,
        "inventory_item_id": inventory_item_id,
        "available": int(available),
    }
    async with await _client(credential_id, db) as client:
        r = await client.post("/inventory_levels/set.json", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------

@register_node("shopify.get_customer")
async def shopify_get_customer(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /customers/{id}.json — fetch a single customer."""
    customer_id = config.get("customer_id") or input_data.get("customer_id")
    if not customer_id:
        raise ValueError("shopify.get_customer requires 'customer_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/customers/{customer_id}.json")
    return _check(r)


@register_node("shopify.list_customers")
async def shopify_list_customers(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /customers.json — list customers."""
    params = {}
    limit = config.get("limit") or input_data.get("limit")
    if limit:
        params["limit"] = min(int(limit), 250)
    since_id = config.get("since_id") or input_data.get("since_id")
    if since_id:
        params["since_id"] = since_id
    async with await _client(credential_id, db) as client:
        r = await client.get("/customers.json", params=params)
    return _check(r)


@register_node("shopify.search_customers")
async def shopify_search_customers(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /customers/search.json — search customers by query string."""
    query = config.get("query") or input_data.get("query")
    if not query:
        raise ValueError("shopify.search_customers requires 'query'")
    async with await _client(credential_id, db) as client:
        r = await client.get("/customers/search.json", params={"query": query})
    return _check(r)


@register_node("shopify.create_customer")
async def shopify_create_customer(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /customers.json — create a new customer."""
    email = config.get("email") or input_data.get("email")
    if not email:
        raise ValueError("shopify.create_customer requires 'email'")
    customer: dict = {"email": email}
    for field in ("first_name", "last_name", "phone", "accepts_marketing"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            customer[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/customers.json", json={"customer": customer})
    return _check(r)


# ---------------------------------------------------------------------------
# Shop / Misc
# ---------------------------------------------------------------------------

@register_node("shopify.get_shop_info")
async def shopify_get_shop_info(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /shop.json — return shop details."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/shop.json")
    return _check(r)


@register_node("shopify.create_discount_code")
async def shopify_create_discount_code(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /price_rules/{id}/discount_codes.json — create a discount code under a price rule."""
    price_rule_id = config.get("price_rule_id") or input_data.get("price_rule_id")
    code = config.get("code") or input_data.get("code")
    if not price_rule_id or not code:
        raise ValueError("shopify.create_discount_code requires 'price_rule_id' and 'code'")
    async with await _client(credential_id, db) as client:
        r = await client.post(
            f"/price_rules/{price_rule_id}/discount_codes.json",
            json={"discount_code": {"code": code}},
        )
    return _check(r)


@register_node("shopify.list_webhooks")
async def shopify_list_webhooks(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /webhooks.json — list all registered webhooks."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/webhooks.json")
    return _check(r)
