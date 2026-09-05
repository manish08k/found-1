"""Cashfree Payments integration — orders and payments (India)."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

CASHFREE_BASE = "https://api.cashfree.com/pg"
CASHFREE_API_VERSION = "2023-08-01"


def _headers(app_id: str, secret_key: str) -> dict:
    return {
        "x-client-id": app_id,
        "x-client-secret": secret_key,
        "x-api-version": CASHFREE_API_VERSION,
        "Content-Type": "application/json",
    }


@register_node("cashfree_payments.create_order")
async def cashfree_create_order(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new Cashfree order.

    config/input_data:
      app_id          — Cashfree App ID (required)
      secret_key      — Cashfree Secret Key (required)
      order_id        — Unique order ID (required)
      order_amount    — Order amount (required)
      order_currency  — Currency code (default "INR")
      customer_id     — Customer ID (required)
      customer_phone  — Customer phone number (required)
    """
    app_id = config.get("app_id") or input_data.get("app_id")
    secret_key = config.get("secret_key") or input_data.get("secret_key")
    order_id = config.get("order_id") or input_data.get("order_id")
    order_amount = config.get("order_amount") or input_data.get("order_amount")
    customer_id = config.get("customer_id") or input_data.get("customer_id")
    customer_phone = config.get("customer_phone") or input_data.get("customer_phone")

    if not app_id:
        raise ValueError("app_id is required for cashfree_payments.create_order")
    if not secret_key:
        raise ValueError("secret_key is required for cashfree_payments.create_order")
    if not order_id:
        raise ValueError("order_id is required for cashfree_payments.create_order")
    if not order_amount:
        raise ValueError("order_amount is required for cashfree_payments.create_order")
    if not customer_id:
        raise ValueError("customer_id is required for cashfree_payments.create_order")
    if not customer_phone:
        raise ValueError("customer_phone is required for cashfree_payments.create_order")

    currency = config.get("order_currency", "INR")
    payload = {
        "order_id": order_id,
        "order_amount": float(order_amount),
        "order_currency": currency,
        "customer_details": {
            "customer_id": customer_id,
            "customer_phone": customer_phone,
        },
    }

    async with httpx.AsyncClient(base_url=CASHFREE_BASE, timeout=30) as client:
        r = await client.post("/orders", headers=_headers(app_id, secret_key), json=payload)
        r.raise_for_status()
        order = r.json()

    log.info("cashfree_payments.create_order", order_id=order_id, status=order.get("order_status"))
    return {"order": order, "order_id": order_id, "status": order.get("order_status"), "payment_session_id": order.get("payment_session_id")}


@register_node("cashfree_payments.get_order")
async def cashfree_get_order(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a Cashfree order by order ID.

    config/input_data:
      app_id     — Cashfree App ID (required)
      secret_key — Cashfree Secret Key (required)
      order_id   — Order ID to fetch (required)
    """
    app_id = config.get("app_id") or input_data.get("app_id")
    secret_key = config.get("secret_key") or input_data.get("secret_key")
    order_id = config.get("order_id") or input_data.get("order_id")

    if not app_id:
        raise ValueError("app_id is required for cashfree_payments.get_order")
    if not secret_key:
        raise ValueError("secret_key is required for cashfree_payments.get_order")
    if not order_id:
        raise ValueError("order_id is required for cashfree_payments.get_order")

    async with httpx.AsyncClient(base_url=CASHFREE_BASE, timeout=30) as client:
        r = await client.get(f"/orders/{order_id}", headers=_headers(app_id, secret_key))
        r.raise_for_status()
        order = r.json()

    log.info("cashfree_payments.get_order", order_id=order_id, status=order.get("order_status"))
    return {"order": order, "order_id": order_id, "status": order.get("order_status"), "amount": order.get("order_amount")}


@register_node("cashfree_payments.list_payments")
async def cashfree_list_payments(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List payments for a given Cashfree order.

    config/input_data:
      app_id     — Cashfree App ID (required)
      secret_key — Cashfree Secret Key (required)
      order_id   — Order ID (required)
    """
    app_id = config.get("app_id") or input_data.get("app_id")
    secret_key = config.get("secret_key") or input_data.get("secret_key")
    order_id = config.get("order_id") or input_data.get("order_id")

    if not app_id:
        raise ValueError("app_id is required for cashfree_payments.list_payments")
    if not secret_key:
        raise ValueError("secret_key is required for cashfree_payments.list_payments")
    if not order_id:
        raise ValueError("order_id is required for cashfree_payments.list_payments")

    async with httpx.AsyncClient(base_url=CASHFREE_BASE, timeout=30) as client:
        r = await client.get(f"/orders/{order_id}/payments", headers=_headers(app_id, secret_key))
        r.raise_for_status()
        payments = r.json()

    if not isinstance(payments, list):
        payments = [payments] if payments else []
    log.info("cashfree_payments.list_payments", order_id=order_id, count=len(payments))
    return {"payments": payments, "order_id": order_id, "count": len(payments)}
