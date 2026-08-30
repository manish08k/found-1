"""
Razorpay payment gateway integration (India).

Credential fields:
  - key_id: Razorpay Key ID (rzp_live_... or rzp_test_...)
  - key_secret: Razorpay Key Secret

Auth: HTTP Basic auth with key_id:key_secret
Base URL: https://api.razorpay.com/v1
"""
import hashlib
import hmac
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

RAZORPAY_BASE = "https://api.razorpay.com/v1"


async def _creds(credential_id: str, db) -> tuple[str, str]:
    creds = await get_credential_data(credential_id, db)
    key_id = creds.get("key_id")
    key_secret = creds.get("key_secret")
    if not key_id:
        raise ValueError("Razorpay credential is missing 'key_id'")
    if not key_secret:
        raise ValueError("Razorpay credential is missing 'key_secret'")
    return key_id, key_secret


def _client(key_id: str, key_secret: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=RAZORPAY_BASE,
        auth=(key_id, key_secret),
        headers={"Content-Type": "application/json"},
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Razorpay API error {r.status_code}: {detail}")
    return r.json()


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

@register_node("razorpay.create_order")
async def razorpay_create_order(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /orders — create a Razorpay order (amount in smallest currency unit)."""
    amount = config.get("amount") or input_data.get("amount")
    if amount is None:
        raise ValueError("razorpay.create_order requires 'amount'")
    currency = config.get("currency") or input_data.get("currency", "INR")
    body: dict = {"amount": int(amount), "currency": currency}
    receipt = config.get("receipt") or input_data.get("receipt")
    if receipt:
        body["receipt"] = receipt
    notes = config.get("notes") or input_data.get("notes")
    if notes:
        body["notes"] = notes
    key_id, key_secret = await _creds(credential_id, db)
    async with _client(key_id, key_secret) as client:
        r = await client.post("/orders", json=body)
    return _check(r)


@register_node("razorpay.get_order")
async def razorpay_get_order(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /orders/{id} — fetch a single order."""
    order_id = config.get("order_id") or input_data.get("order_id")
    if not order_id:
        raise ValueError("razorpay.get_order requires 'order_id'")
    key_id, key_secret = await _creds(credential_id, db)
    async with _client(key_id, key_secret) as client:
        r = await client.get(f"/orders/{order_id}")
    return _check(r)


@register_node("razorpay.list_orders")
async def razorpay_list_orders(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /orders — list orders with optional filters."""
    params: dict = {}
    from_ts = config.get("from_timestamp") or input_data.get("from_timestamp")
    if from_ts:
        params["from"] = int(from_ts)
    to_ts = config.get("to_timestamp") or input_data.get("to_timestamp")
    if to_ts:
        params["to"] = int(to_ts)
    count = config.get("count") or input_data.get("count")
    if count:
        params["count"] = min(int(count), 100)
    skip = config.get("skip") or input_data.get("skip")
    if skip:
        params["skip"] = int(skip)
    key_id, key_secret = await _creds(credential_id, db)
    async with _client(key_id, key_secret) as client:
        r = await client.get("/orders", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------

@register_node("razorpay.get_payment")
async def razorpay_get_payment(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /payments/{id} — fetch a single payment."""
    payment_id = config.get("payment_id") or input_data.get("payment_id")
    if not payment_id:
        raise ValueError("razorpay.get_payment requires 'payment_id'")
    key_id, key_secret = await _creds(credential_id, db)
    async with _client(key_id, key_secret) as client:
        r = await client.get(f"/payments/{payment_id}")
    return _check(r)


@register_node("razorpay.list_payments")
async def razorpay_list_payments(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /payments — list payments with optional filters."""
    params: dict = {}
    from_ts = config.get("from_timestamp") or input_data.get("from_timestamp")
    if from_ts:
        params["from"] = int(from_ts)
    to_ts = config.get("to_timestamp") or input_data.get("to_timestamp")
    if to_ts:
        params["to"] = int(to_ts)
    count = config.get("count") or input_data.get("count")
    if count:
        params["count"] = min(int(count), 100)
    skip = config.get("skip") or input_data.get("skip")
    if skip:
        params["skip"] = int(skip)
    key_id, key_secret = await _creds(credential_id, db)
    async with _client(key_id, key_secret) as client:
        r = await client.get("/payments", params=params)
    return _check(r)


@register_node("razorpay.capture_payment")
async def razorpay_capture_payment(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /payments/{id}/capture — capture an authorized payment."""
    payment_id = config.get("payment_id") or input_data.get("payment_id")
    amount = config.get("amount") or input_data.get("amount")
    if not payment_id or amount is None:
        raise ValueError("razorpay.capture_payment requires 'payment_id' and 'amount'")
    currency = config.get("currency") or input_data.get("currency", "INR")
    body = {"amount": int(amount), "currency": currency}
    key_id, key_secret = await _creds(credential_id, db)
    async with _client(key_id, key_secret) as client:
        r = await client.post(f"/payments/{payment_id}/capture", json=body)
    return _check(r)


@register_node("razorpay.refund_payment")
async def razorpay_refund_payment(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /payments/{id}/refund — refund a payment (full or partial)."""
    payment_id = config.get("payment_id") or input_data.get("payment_id")
    if not payment_id:
        raise ValueError("razorpay.refund_payment requires 'payment_id'")
    body: dict = {}
    amount = config.get("amount") or input_data.get("amount")
    if amount is not None:
        body["amount"] = int(amount)
    notes = config.get("notes") or input_data.get("notes")
    if notes:
        body["notes"] = notes
    key_id, key_secret = await _creds(credential_id, db)
    async with _client(key_id, key_secret) as client:
        r = await client.post(f"/payments/{payment_id}/refund", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Refunds
# ---------------------------------------------------------------------------

@register_node("razorpay.create_refund")
async def razorpay_create_refund(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /refunds — create a refund directly (requires payment_id + amount)."""
    payment_id = config.get("payment_id") or input_data.get("payment_id")
    amount = config.get("amount") or input_data.get("amount")
    if not payment_id or amount is None:
        raise ValueError("razorpay.create_refund requires 'payment_id' and 'amount'")
    body: dict = {"payment_id": payment_id, "amount": int(amount)}
    notes = config.get("notes") or input_data.get("notes")
    if notes:
        body["notes"] = notes
    key_id, key_secret = await _creds(credential_id, db)
    async with _client(key_id, key_secret) as client:
        r = await client.post("/refunds", json=body)
    return _check(r)


@register_node("razorpay.get_refund")
async def razorpay_get_refund(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /refunds/{id} — fetch a single refund."""
    refund_id = config.get("refund_id") or input_data.get("refund_id")
    if not refund_id:
        raise ValueError("razorpay.get_refund requires 'refund_id'")
    key_id, key_secret = await _creds(credential_id, db)
    async with _client(key_id, key_secret) as client:
        r = await client.get(f"/refunds/{refund_id}")
    return _check(r)


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------

@register_node("razorpay.create_subscription")
async def razorpay_create_subscription(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /subscriptions — create a subscription."""
    plan_id = config.get("plan_id") or input_data.get("plan_id")
    total_count = config.get("total_count") or input_data.get("total_count")
    if not plan_id or total_count is None:
        raise ValueError("razorpay.create_subscription requires 'plan_id' and 'total_count'")
    body: dict = {"plan_id": plan_id, "total_count": int(total_count)}
    customer_notify = config.get("customer_notify")
    if customer_notify is None:
        customer_notify = input_data.get("customer_notify")
    if customer_notify is not None:
        body["customer_notify"] = int(bool(customer_notify))
    start_at = config.get("start_at") or input_data.get("start_at")
    if start_at:
        body["start_at"] = int(start_at)
    quantity = config.get("quantity") or input_data.get("quantity")
    if quantity:
        body["quantity"] = int(quantity)
    key_id, key_secret = await _creds(credential_id, db)
    async with _client(key_id, key_secret) as client:
        r = await client.post("/subscriptions", json=body)
    return _check(r)


@register_node("razorpay.get_subscription")
async def razorpay_get_subscription(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /subscriptions/{id} — fetch a subscription."""
    subscription_id = config.get("subscription_id") or input_data.get("subscription_id")
    if not subscription_id:
        raise ValueError("razorpay.get_subscription requires 'subscription_id'")
    key_id, key_secret = await _creds(credential_id, db)
    async with _client(key_id, key_secret) as client:
        r = await client.get(f"/subscriptions/{subscription_id}")
    return _check(r)


@register_node("razorpay.cancel_subscription")
async def razorpay_cancel_subscription(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /subscriptions/{id}/cancel — cancel a subscription."""
    subscription_id = config.get("subscription_id") or input_data.get("subscription_id")
    if not subscription_id:
        raise ValueError("razorpay.cancel_subscription requires 'subscription_id'")
    cancel_at_cycle_end = config.get("cancel_at_cycle_end")
    if cancel_at_cycle_end is None:
        cancel_at_cycle_end = input_data.get("cancel_at_cycle_end", False)
    body = {"cancel_at_cycle_end": 1 if cancel_at_cycle_end else 0}
    key_id, key_secret = await _creds(credential_id, db)
    async with _client(key_id, key_secret) as client:
        r = await client.post(f"/subscriptions/{subscription_id}/cancel", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------

@register_node("razorpay.create_plan")
async def razorpay_create_plan(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /plans — create a billing plan."""
    period = config.get("period") or input_data.get("period")
    interval = config.get("interval") or input_data.get("interval")
    item = config.get("item") or input_data.get("item")
    if not period or interval is None or not item:
        raise ValueError("razorpay.create_plan requires 'period', 'interval', and 'item'")
    body = {"period": period, "interval": int(interval), "item": item}
    key_id, key_secret = await _creds(credential_id, db)
    async with _client(key_id, key_secret) as client:
        r = await client.post("/plans", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Transfers
# ---------------------------------------------------------------------------

@register_node("razorpay.transfer_payment")
async def razorpay_transfer_payment(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /payments/{id}/transfer — transfer payment to linked accounts."""
    payment_id = config.get("payment_id") or input_data.get("payment_id")
    transfers = config.get("transfers") or input_data.get("transfers")
    if not payment_id or not transfers:
        raise ValueError("razorpay.transfer_payment requires 'payment_id' and 'transfers'")
    body = {"transfers": transfers}
    key_id, key_secret = await _creds(credential_id, db)
    async with _client(key_id, key_secret) as client:
        r = await client.post(f"/payments/{payment_id}/transfer", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Signature Verification
# ---------------------------------------------------------------------------

@register_node("razorpay.verify_payment_signature")
async def razorpay_verify_payment_signature(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Verify HMAC-SHA256 webhook signature.

    Computes HMAC over '{razorpay_order_id}|{razorpay_payment_id}' using
    key_secret and compares to razorpay_signature. Returns {valid: bool}.
    """
    order_id = config.get("razorpay_order_id") or input_data.get("razorpay_order_id")
    payment_id = config.get("razorpay_payment_id") or input_data.get("razorpay_payment_id")
    signature = config.get("razorpay_signature") or input_data.get("razorpay_signature")
    if not order_id or not payment_id or not signature:
        raise ValueError(
            "razorpay.verify_payment_signature requires 'razorpay_order_id', "
            "'razorpay_payment_id', and 'razorpay_signature'"
        )
    _key_id, key_secret = await _creds(credential_id, db)
    message = f"{order_id}|{payment_id}"
    expected = hmac.new(key_secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    valid = hmac.compare_digest(expected, signature)
    return {"valid": valid}
