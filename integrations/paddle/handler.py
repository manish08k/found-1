"""
Paddle billing integration.

Credential fields:
  - api_key: Paddle API key
  - sandbox: boolean (default false)

Auth: Authorization: Bearer {api_key}
Base URL: https://api.paddle.com (live) or https://sandbox-api.paddle.com (sandbox)
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    sandbox = creds.get("sandbox", False)
    if isinstance(sandbox, str):
        sandbox = sandbox.lower() in ("true", "1", "yes")
    if not api_key:
        raise ValueError("Paddle credential is missing 'api_key'")
    base_url = "https://sandbox-api.paddle.com" if sandbox else "https://api.paddle.com"
    return httpx.AsyncClient(
        base_url=base_url,
        headers={
            "Authorization": f"Bearer {api_key}",
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
        raise ValueError(f"Paddle API error {r.status_code}: {detail}")
    return r.json()


async def test_connection(credential_id: str, db) -> dict:
    """Verify credentials by listing products."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/products", params={"per_page": 1})
    data = _check(r)
    return {"ok": True, "data_count": len(data.get("data", []))}


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

@register_node("paddle.list_products")
async def paddle_list_products(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /products — list products."""
    params = {}
    for key in ("after", "per_page", "status", "tax_category", "type", "id"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/products", params=params)
    return _check(r)


@register_node("paddle.get_product")
async def paddle_get_product(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /products/{id} — get a product."""
    product_id = config.get("product_id") or input_data.get("product_id")
    if not product_id:
        raise ValueError("paddle.get_product requires 'product_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/products/{product_id}")
    return _check(r)


@register_node("paddle.create_product")
async def paddle_create_product(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /products — create a product."""
    name = config.get("name") or input_data.get("name")
    tax_category = config.get("tax_category") or input_data.get("tax_category")
    if not name:
        raise ValueError("paddle.create_product requires 'name'")
    if not tax_category:
        raise ValueError("paddle.create_product requires 'tax_category'")
    body: dict = {"name": name, "tax_category": tax_category}
    for field in ("description", "image_url", "custom_data", "type"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/products", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Prices
# ---------------------------------------------------------------------------

@register_node("paddle.list_prices")
async def paddle_list_prices(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /prices — list prices."""
    params = {}
    for key in ("after", "per_page", "status", "product_id", "recurring", "id"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/prices", params=params)
    return _check(r)


@register_node("paddle.create_price")
async def paddle_create_price(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /prices — create a price."""
    product_id = config.get("product_id") or input_data.get("product_id")
    description = config.get("description") or input_data.get("description")
    unit_price = config.get("unit_price") or input_data.get("unit_price")
    if not product_id or not description or not unit_price:
        raise ValueError("paddle.create_price requires 'product_id', 'description', and 'unit_price'")
    body: dict = {"product_id": product_id, "description": description, "unit_price": unit_price}
    for field in ("name", "trial_period", "billing_cycle", "quantity", "tax_mode", "custom_data"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/prices", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------

@register_node("paddle.list_customers")
async def paddle_list_customers(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /customers — list customers."""
    params = {}
    for key in ("after", "per_page", "status", "email", "id"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/customers", params=params)
    return _check(r)


@register_node("paddle.get_customer")
async def paddle_get_customer(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /customers/{id} — get a customer."""
    customer_id = config.get("customer_id") or input_data.get("customer_id")
    if not customer_id:
        raise ValueError("paddle.get_customer requires 'customer_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/customers/{customer_id}")
    return _check(r)


@register_node("paddle.create_customer")
async def paddle_create_customer(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /customers — create a customer."""
    email = config.get("email") or input_data.get("email")
    if not email:
        raise ValueError("paddle.create_customer requires 'email'")
    body: dict = {"email": email}
    for field in ("name", "locale", "custom_data"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/customers", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------

@register_node("paddle.list_subscriptions")
async def paddle_list_subscriptions(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /subscriptions — list subscriptions."""
    params = {}
    for key in ("after", "per_page", "status", "customer_id", "price_id", "id"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/subscriptions", params=params)
    return _check(r)


@register_node("paddle.get_subscription")
async def paddle_get_subscription(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /subscriptions/{id} — get a subscription."""
    subscription_id = config.get("subscription_id") or input_data.get("subscription_id")
    if not subscription_id:
        raise ValueError("paddle.get_subscription requires 'subscription_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/subscriptions/{subscription_id}")
    return _check(r)


@register_node("paddle.cancel_subscription")
async def paddle_cancel_subscription(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /subscriptions/{id}/cancel — cancel a subscription."""
    subscription_id = config.get("subscription_id") or input_data.get("subscription_id")
    if not subscription_id:
        raise ValueError("paddle.cancel_subscription requires 'subscription_id'")
    effective_from = config.get("effective_from", input_data.get("effective_from", "next_billing_period"))
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/subscriptions/{subscription_id}/cancel", json={"effective_from": effective_from})
    return _check(r)


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

@register_node("paddle.list_transactions")
async def paddle_list_transactions(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /transactions — list transactions."""
    params = {}
    for key in ("after", "per_page", "status", "customer_id", "subscription_id", "id",
                "billed_at", "created_at", "updated_at"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/transactions", params=params)
    return _check(r)


@register_node("paddle.get_transaction")
async def paddle_get_transaction(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /transactions/{id} — get a transaction."""
    transaction_id = config.get("transaction_id") or input_data.get("transaction_id")
    if not transaction_id:
        raise ValueError("paddle.get_transaction requires 'transaction_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/transactions/{transaction_id}")
    return _check(r)


# ---------------------------------------------------------------------------
# Discounts
# ---------------------------------------------------------------------------

@register_node("paddle.list_discounts")
async def paddle_list_discounts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /discounts — list discounts."""
    params = {}
    for key in ("after", "per_page", "status", "code", "id"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/discounts", params=params)
    return _check(r)
