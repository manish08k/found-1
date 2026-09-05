"""Unleashed Software ERP integration with HMAC-SHA256 authentication."""
import base64
import hashlib
import hmac

import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

UNLEASHED_BASE = "https://api.unleashedsoftware.com"


def _make_signature(api_key: str, query_string: str) -> str:
    """Generate HMAC-SHA256 signature for Unleashed API."""
    return base64.b64encode(
        hmac.new(api_key.encode(), query_string.encode(), hashlib.sha256).digest()
    ).decode()


def _build_headers(api_id: str, api_key: str, query_string: str = "") -> dict:
    """Build Unleashed auth headers."""
    signature = _make_signature(api_key, query_string)
    return {
        "api-auth-id": api_id,
        "api-auth-signature": signature,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


@register_node("unleashedsoftware.list_products")
async def list_products(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all products from Unleashed Software.

    config:
      api_id  — Unleashed API ID (required)
      api_key — Unleashed API key (required)
    """
    merged = {**config, **input_data}
    api_id = merged.get("api_id") or ""
    api_key = merged.get("api_key") or ""

    if not api_id or not api_key:
        raise ValueError("api_id and api_key are required for unleashedsoftware.list_products")

    query_string = "format=json"
    headers = _build_headers(api_id, api_key, query_string)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{UNLEASHED_BASE}/Products/1", headers=headers, params={"format": "json"})
        r.raise_for_status()
        data = r.json()

    items = data.get("Items", data)
    log.info("unleashedsoftware.list_products", count=len(items) if isinstance(items, list) else 0)
    return {"products": items, "pagination": data.get("Pagination", {})}


@register_node("unleashedsoftware.get_product")
async def get_product(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single product by product code.

    config/input_data:
      api_id       — Unleashed API ID (required)
      api_key      — Unleashed API key (required)
      product_code — product code (required)
    """
    merged = {**config, **input_data}
    api_id = merged.get("api_id") or ""
    api_key = merged.get("api_key") or ""
    product_code = merged.get("product_code") or ""

    if not api_id or not api_key:
        raise ValueError("api_id and api_key are required for unleashedsoftware.get_product")
    if not product_code:
        raise ValueError("product_code is required for unleashedsoftware.get_product")

    query_string = "format=json"
    headers = _build_headers(api_id, api_key, query_string)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{UNLEASHED_BASE}/Products/{product_code}",
            headers=headers,
            params={"format": "json"},
        )
        r.raise_for_status()
        data = r.json()

    items = data.get("Items", [data])
    product = items[0] if items else data
    log.info("unleashedsoftware.get_product", product_code=product_code)
    return {"product": product}


@register_node("unleashedsoftware.list_customers")
async def list_customers(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all customers from Unleashed Software.

    config:
      api_id  — Unleashed API ID (required)
      api_key — Unleashed API key (required)
    """
    merged = {**config, **input_data}
    api_id = merged.get("api_id") or ""
    api_key = merged.get("api_key") or ""

    if not api_id or not api_key:
        raise ValueError("api_id and api_key are required for unleashedsoftware.list_customers")

    query_string = "format=json"
    headers = _build_headers(api_id, api_key, query_string)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{UNLEASHED_BASE}/Customers/1", headers=headers, params={"format": "json"})
        r.raise_for_status()
        data = r.json()

    items = data.get("Items", data)
    log.info("unleashedsoftware.list_customers", count=len(items) if isinstance(items, list) else 0)
    return {"customers": items, "pagination": data.get("Pagination", {})}


@register_node("unleashedsoftware.get_customer")
async def get_customer(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single customer by customer code.

    config/input_data:
      api_id        — Unleashed API ID (required)
      api_key       — Unleashed API key (required)
      customer_code — customer code (required)
    """
    merged = {**config, **input_data}
    api_id = merged.get("api_id") or ""
    api_key = merged.get("api_key") or ""
    customer_code = merged.get("customer_code") or ""

    if not api_id or not api_key:
        raise ValueError("api_id and api_key are required for unleashedsoftware.get_customer")
    if not customer_code:
        raise ValueError("customer_code is required for unleashedsoftware.get_customer")

    query_string = "format=json"
    headers = _build_headers(api_id, api_key, query_string)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{UNLEASHED_BASE}/Customers/{customer_code}",
            headers=headers,
            params={"format": "json"},
        )
        r.raise_for_status()
        data = r.json()

    items = data.get("Items", [data])
    customer = items[0] if items else data
    log.info("unleashedsoftware.get_customer", customer_code=customer_code)
    return {"customer": customer}


@register_node("unleashedsoftware.list_sales_orders")
async def list_sales_orders(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all sales orders from Unleashed Software.

    config:
      api_id  — Unleashed API ID (required)
      api_key — Unleashed API key (required)
    """
    merged = {**config, **input_data}
    api_id = merged.get("api_id") or ""
    api_key = merged.get("api_key") or ""

    if not api_id or not api_key:
        raise ValueError("api_id and api_key are required for unleashedsoftware.list_sales_orders")

    query_string = "format=json"
    headers = _build_headers(api_id, api_key, query_string)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{UNLEASHED_BASE}/SalesOrders/1", headers=headers, params={"format": "json"})
        r.raise_for_status()
        data = r.json()

    items = data.get("Items", data)
    log.info("unleashedsoftware.list_sales_orders", count=len(items) if isinstance(items, list) else 0)
    return {"sales_orders": items, "pagination": data.get("Pagination", {})}
