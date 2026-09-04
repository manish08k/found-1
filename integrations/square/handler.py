"""
Square payments integration.

Credential fields:
  - access_token: Square access token
  - sandbox: boolean (default false)

Auth: Authorization: Bearer {access_token}
Base URL: https://connect.squareup.com (live) or https://connect.squareupsandbox.com (sandbox)
API version header: Square-Version: 2024-11-20
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

SQUARE_API_VERSION = "2024-11-20"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    access_token = creds.get("access_token")
    sandbox = creds.get("sandbox", False)
    if isinstance(sandbox, str):
        sandbox = sandbox.lower() in ("true", "1", "yes")
    if not access_token:
        raise ValueError("Square credential is missing 'access_token'")
    base_url = "https://connect.squareupsandbox.com" if sandbox else "https://connect.squareup.com"
    return httpx.AsyncClient(
        base_url=base_url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Square-Version": SQUARE_API_VERSION,
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
        raise ValueError(f"Square API error {r.status_code}: {detail}")
    return r.json()


async def test_connection(credential_id: str, db) -> dict:
    """Verify credentials by listing locations."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/v2/locations")
    data = _check(r)
    locations = data.get("locations", [])
    return {"ok": True, "location_count": len(locations)}


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

@register_node("square.list_locations")
async def square_list_locations(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /v2/locations — list all locations."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/v2/locations")
    return _check(r)


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------

@register_node("square.list_customers")
async def square_list_customers(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /v2/customers — list customers."""
    params = {}
    for key in ("cursor", "limit", "sort_field", "sort_order"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/v2/customers", params=params)
    return _check(r)


@register_node("square.create_customer")
async def square_create_customer(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /v2/customers — create a customer."""
    body: dict = {}
    for field in ("given_name", "family_name", "email_address", "phone_number",
                  "company_name", "nickname", "note", "reference_id"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            body[field] = v
    if not body:
        raise ValueError("square.create_customer requires at least one field (e.g. 'email_address')")
    import uuid
    body["idempotency_key"] = config.get("idempotency_key") or input_data.get("idempotency_key") or str(uuid.uuid4())
    async with await _client(credential_id, db) as client:
        r = await client.post("/v2/customers", json=body)
    return _check(r)


@register_node("square.get_customer")
async def square_get_customer(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /v2/customers/{id} — get a customer."""
    customer_id = config.get("customer_id") or input_data.get("customer_id")
    if not customer_id:
        raise ValueError("square.get_customer requires 'customer_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/v2/customers/{customer_id}")
    return _check(r)


@register_node("square.update_customer")
async def square_update_customer(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /v2/customers/{id} — update a customer."""
    customer_id = config.get("customer_id") or input_data.get("customer_id")
    if not customer_id:
        raise ValueError("square.update_customer requires 'customer_id'")
    body: dict = {}
    for field in ("given_name", "family_name", "email_address", "phone_number",
                  "company_name", "nickname", "note", "reference_id"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.put(f"/v2/customers/{customer_id}", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

@register_node("square.list_orders")
async def square_list_orders(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /v2/orders/search — search/list orders."""
    location_ids = config.get("location_ids") or input_data.get("location_ids")
    if not location_ids:
        raise ValueError("square.list_orders requires 'location_ids'")
    body: dict = {"location_ids": location_ids if isinstance(location_ids, list) else [location_ids]}
    query = config.get("query") or input_data.get("query")
    if query:
        body["query"] = query
    limit = config.get("limit") or input_data.get("limit")
    if limit:
        body["limit"] = int(limit)
    cursor = config.get("cursor") or input_data.get("cursor")
    if cursor:
        body["cursor"] = cursor
    async with await _client(credential_id, db) as client:
        r = await client.post("/v2/orders/search", json=body)
    return _check(r)


@register_node("square.create_order")
async def square_create_order(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /v2/orders — create an order."""
    location_id = config.get("location_id") or input_data.get("location_id")
    if not location_id:
        raise ValueError("square.create_order requires 'location_id'")
    import uuid
    idempotency_key = config.get("idempotency_key") or input_data.get("idempotency_key") or str(uuid.uuid4())
    order: dict = {"location_id": location_id}
    for field in ("line_items", "taxes", "discounts", "fulfillments", "reference_id", "customer_id"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            order[field] = v
    body = {"order": order, "idempotency_key": idempotency_key}
    async with await _client(credential_id, db) as client:
        r = await client.post("/v2/orders", json=body)
    return _check(r)


@register_node("square.get_order")
async def square_get_order(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /v2/orders/{id} — get an order."""
    order_id = config.get("order_id") or input_data.get("order_id")
    if not order_id:
        raise ValueError("square.get_order requires 'order_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/v2/orders/{order_id}")
    return _check(r)


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------

@register_node("square.list_payments")
async def square_list_payments(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /v2/payments — list payments."""
    params = {}
    for key in ("cursor", "limit", "location_id", "begin_time", "end_time", "sort_order"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/v2/payments", params=params)
    return _check(r)


@register_node("square.create_payment")
async def square_create_payment(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /v2/payments — create a payment."""
    source_id = config.get("source_id") or input_data.get("source_id")
    amount_money = config.get("amount_money") or input_data.get("amount_money")
    if not source_id or not amount_money:
        raise ValueError("square.create_payment requires 'source_id' and 'amount_money'")
    import uuid
    idempotency_key = config.get("idempotency_key") or input_data.get("idempotency_key") or str(uuid.uuid4())
    body: dict = {
        "source_id": source_id,
        "amount_money": amount_money,
        "idempotency_key": idempotency_key,
    }
    for field in ("tip_money", "app_fee_money", "delay_duration", "autocomplete",
                  "order_id", "customer_id", "location_id", "reference_id", "note"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/v2/payments", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

@register_node("square.list_catalog")
async def square_list_catalog(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /v2/catalog/list — list catalog objects."""
    params = {}
    for key in ("cursor", "limit", "types"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/v2/catalog/list", params=params)
    return _check(r)


@register_node("square.create_catalog_item")
async def square_create_catalog_item(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /v2/catalog/object — create a catalog item."""
    import uuid
    idempotency_key = config.get("idempotency_key") or input_data.get("idempotency_key") or str(uuid.uuid4())
    catalog_object = config.get("object") or input_data.get("object")
    if not catalog_object:
        name = config.get("name") or input_data.get("name")
        if not name:
            raise ValueError("square.create_catalog_item requires 'object' or 'name'")
        catalog_object = {
            "type": "ITEM",
            "id": f"#new-item-{uuid.uuid4().hex[:8]}",
            "item_data": {
                "name": name,
                "description": config.get("description") or input_data.get("description", ""),
            },
        }
        variations = config.get("variations") or input_data.get("variations")
        if variations:
            catalog_object["item_data"]["variations"] = variations
    body = {"idempotency_key": idempotency_key, "object": catalog_object}
    async with await _client(credential_id, db) as client:
        r = await client.post("/v2/catalog/object", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

@register_node("square.list_inventory")
async def square_list_inventory(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /v2/inventory/counts/batch-retrieve — retrieve inventory counts."""
    catalog_object_ids = config.get("catalog_object_ids") or input_data.get("catalog_object_ids")
    location_ids = config.get("location_ids") or input_data.get("location_ids")
    body: dict = {}
    if catalog_object_ids:
        body["catalog_object_ids"] = catalog_object_ids if isinstance(catalog_object_ids, list) else [catalog_object_ids]
    if location_ids:
        body["location_ids"] = location_ids if isinstance(location_ids, list) else [location_ids]
    cursor = config.get("cursor") or input_data.get("cursor")
    if cursor:
        body["cursor"] = cursor
    async with await _client(credential_id, db) as client:
        r = await client.post("/v2/inventory/counts/batch-retrieve", json=body)
    return _check(r)
