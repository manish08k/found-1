"""
PayPal integration.

Credential fields:
  - client_id: PayPal client ID
  - client_secret: PayPal client secret
  - sandbox: boolean (default false)

Auth: OAuth2 client credentials (fetch token first, then Bearer)
Base URL: https://api-m.paypal.com (live) or https://api-m.sandbox.paypal.com (sandbox)
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _get_paypal_token(client_id: str, client_secret: str, base_url: str) -> str:
    """Fetch a PayPal OAuth2 access token using client credentials."""
    async with httpx.AsyncClient(base_url=base_url) as client:
        r = await client.post(
            "/v1/oauth2/token",
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
        )
        if not r.is_success:
            raise ValueError(f"PayPal auth failed: {r.status_code}")
        return r.json()["access_token"]


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    client_id = creds.get("client_id")
    client_secret = creds.get("client_secret")
    sandbox = creds.get("sandbox", False)
    if isinstance(sandbox, str):
        sandbox = sandbox.lower() in ("true", "1", "yes")
    if not client_id:
        raise ValueError("PayPal credential is missing 'client_id'")
    if not client_secret:
        raise ValueError("PayPal credential is missing 'client_secret'")
    base_url = "https://api-m.sandbox.paypal.com" if sandbox else "https://api-m.paypal.com"
    access_token = await _get_paypal_token(client_id, client_secret, base_url)
    return httpx.AsyncClient(
        base_url=base_url,
        headers={
            "Authorization": f"Bearer {access_token}",
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
        raise ValueError(f"PayPal API error {r.status_code}: {detail}")
    if r.status_code == 204 or not r.content:
        return {"success": True}
    return r.json()


async def test_connection(credential_id: str, db) -> dict:
    """Verify credentials by fetching an OAuth token."""
    creds = await get_credential_data(credential_id, db)
    client_id = creds.get("client_id")
    client_secret = creds.get("client_secret")
    sandbox = creds.get("sandbox", False)
    if isinstance(sandbox, str):
        sandbox = sandbox.lower() in ("true", "1", "yes")
    base_url = "https://api-m.sandbox.paypal.com" if sandbox else "https://api-m.paypal.com"
    token = await _get_paypal_token(client_id, client_secret, base_url)
    return {"ok": True, "sandbox": sandbox, "token_preview": token[:10] + "..."}


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

@register_node("paypal.create_order")
async def paypal_create_order(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /v2/checkout/orders — create a PayPal order."""
    intent = config.get("intent", input_data.get("intent", "CAPTURE"))
    purchase_units = config.get("purchase_units") or input_data.get("purchase_units")
    if not purchase_units:
        raise ValueError("paypal.create_order requires 'purchase_units'")
    body: dict = {"intent": intent, "purchase_units": purchase_units}
    application_context = config.get("application_context") or input_data.get("application_context")
    if application_context:
        body["application_context"] = application_context
    async with await _client(credential_id, db) as client:
        r = await client.post("/v2/checkout/orders", json=body)
    return _check(r)


@register_node("paypal.get_order")
async def paypal_get_order(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /v2/checkout/orders/{id} — get an order."""
    order_id = config.get("order_id") or input_data.get("order_id")
    if not order_id:
        raise ValueError("paypal.get_order requires 'order_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/v2/checkout/orders/{order_id}")
    return _check(r)


@register_node("paypal.capture_order")
async def paypal_capture_order(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /v2/checkout/orders/{id}/capture — capture a PayPal order."""
    order_id = config.get("order_id") or input_data.get("order_id")
    if not order_id:
        raise ValueError("paypal.capture_order requires 'order_id'")
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/v2/checkout/orders/{order_id}/capture", json={})
    return _check(r)


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------

@register_node("paypal.create_payment")
async def paypal_create_payment(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /v1/payments/payment — create a payment (legacy v1)."""
    intent = config.get("intent", input_data.get("intent", "sale"))
    payer = config.get("payer") or input_data.get("payer")
    transactions = config.get("transactions") or input_data.get("transactions")
    redirect_urls = config.get("redirect_urls") or input_data.get("redirect_urls")
    if not transactions:
        raise ValueError("paypal.create_payment requires 'transactions'")
    body: dict = {"intent": intent, "transactions": transactions}
    if payer:
        body["payer"] = payer
    if redirect_urls:
        body["redirect_urls"] = redirect_urls
    async with await _client(credential_id, db) as client:
        r = await client.post("/v1/payments/payment", json=body)
    return _check(r)


@register_node("paypal.get_payment")
async def paypal_get_payment(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /v1/payments/payment/{id} — get a payment."""
    payment_id = config.get("payment_id") or input_data.get("payment_id")
    if not payment_id:
        raise ValueError("paypal.get_payment requires 'payment_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/v1/payments/payment/{payment_id}")
    return _check(r)


@register_node("paypal.list_payments")
async def paypal_list_payments(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /v1/payments/payment — list payments."""
    params = {}
    for key in ("count", "start_id", "start_index", "start_time", "end_time", "sort_by", "sort_order"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/v1/payments/payment", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------

@register_node("paypal.create_invoice")
async def paypal_create_invoice(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /v2/invoicing/invoices — create an invoice."""
    detail = config.get("detail") or input_data.get("detail")
    invoicer = config.get("invoicer") or input_data.get("invoicer")
    primary_recipients = config.get("primary_recipients") or input_data.get("primary_recipients")
    if not detail:
        raise ValueError("paypal.create_invoice requires 'detail'")
    body: dict = {"detail": detail}
    if invoicer:
        body["invoicer"] = invoicer
    if primary_recipients:
        body["primary_recipients"] = primary_recipients
    items = config.get("items") or input_data.get("items")
    if items:
        body["items"] = items
    async with await _client(credential_id, db) as client:
        r = await client.post("/v2/invoicing/invoices", json=body)
    return _check(r)


@register_node("paypal.get_invoice")
async def paypal_get_invoice(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /v2/invoicing/invoices/{id} — get an invoice."""
    invoice_id = config.get("invoice_id") or input_data.get("invoice_id")
    if not invoice_id:
        raise ValueError("paypal.get_invoice requires 'invoice_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/v2/invoicing/invoices/{invoice_id}")
    return _check(r)


@register_node("paypal.list_invoices")
async def paypal_list_invoices(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /v2/invoicing/search-invoices — search/list invoices."""
    params = {}
    page = config.get("page") or input_data.get("page")
    if page:
        params["page"] = page
    page_size = config.get("page_size") or input_data.get("page_size")
    if page_size:
        params["page_size"] = page_size
    body: dict = {}
    for key in ("recipient_email", "status", "start_invoice_date", "end_invoice_date"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            body[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/v2/invoicing/search-invoices", json=body, params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------

@register_node("paypal.create_subscription")
async def paypal_create_subscription(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /v1/billing/subscriptions — create a subscription."""
    plan_id = config.get("plan_id") or input_data.get("plan_id")
    if not plan_id:
        raise ValueError("paypal.create_subscription requires 'plan_id'")
    body: dict = {"plan_id": plan_id}
    for key in ("start_time", "subscriber", "application_context", "quantity"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            body[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/v1/billing/subscriptions", json=body)
    return _check(r)


@register_node("paypal.get_subscription")
async def paypal_get_subscription(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /v1/billing/subscriptions/{id} — get a subscription."""
    subscription_id = config.get("subscription_id") or input_data.get("subscription_id")
    if not subscription_id:
        raise ValueError("paypal.get_subscription requires 'subscription_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/v1/billing/subscriptions/{subscription_id}")
    return _check(r)


@register_node("paypal.cancel_subscription")
async def paypal_cancel_subscription(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /v1/billing/subscriptions/{id}/cancel — cancel a subscription."""
    subscription_id = config.get("subscription_id") or input_data.get("subscription_id")
    if not subscription_id:
        raise ValueError("paypal.cancel_subscription requires 'subscription_id'")
    reason = config.get("reason", input_data.get("reason", "Not needed"))
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/v1/billing/subscriptions/{subscription_id}/cancel", json={"reason": reason})
    if r.status_code == 204:
        return {"cancelled": True, "subscription_id": subscription_id}
    return _check(r)


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

@register_node("paypal.list_products")
async def paypal_list_products(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /v1/catalogs/products — list products."""
    params = {}
    for key in ("page_size", "page", "total_required"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/v1/catalogs/products", params=params)
    return _check(r)


@register_node("paypal.create_product")
async def paypal_create_product(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /v1/catalogs/products — create a product."""
    name = config.get("name") or input_data.get("name")
    product_type = config.get("type", input_data.get("type", "SERVICE"))
    if not name:
        raise ValueError("paypal.create_product requires 'name'")
    body: dict = {"name": name, "type": product_type}
    for field in ("description", "id", "category", "image_url", "home_url"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/v1/catalogs/products", json=body)
    return _check(r)
