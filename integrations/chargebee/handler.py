"""
Chargebee billing integration.

Credential fields:
  - api_key: Chargebee API key
  - site: Chargebee subdomain (e.g. "mycompany")

Auth: HTTP Basic with api_key as username and empty password
Base URL: https://{site}.chargebee.com/api/v2
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    site = creds.get("site")
    if not api_key:
        raise ValueError("Chargebee credential is missing 'api_key'")
    if not site:
        raise ValueError("Chargebee credential is missing 'site'")
    base_url = f"https://{site}.chargebee.com/api/v2"
    return httpx.AsyncClient(
        base_url=base_url,
        auth=(api_key, ""),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Chargebee API error {r.status_code}: {detail}")
    return r.json()


async def test_connection(credential_id: str, db) -> dict:
    """Verify credentials by listing one subscription."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/subscriptions", params={"limit": 1})
    data = _check(r)
    return {"ok": True, "list_count": len(data.get("list", []))}


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------

@register_node("chargebee.list_subscriptions")
async def chargebee_list_subscriptions(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /subscriptions — list subscriptions."""
    params = {}
    for key in ("limit", "offset", "status[is]", "customer_id[is]", "plan_id[is]"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/subscriptions", params=params)
    return _check(r)


@register_node("chargebee.get_subscription")
async def chargebee_get_subscription(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /subscriptions/{id} — get a subscription."""
    subscription_id = config.get("subscription_id") or input_data.get("subscription_id")
    if not subscription_id:
        raise ValueError("chargebee.get_subscription requires 'subscription_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/subscriptions/{subscription_id}")
    return _check(r)


@register_node("chargebee.create_subscription")
async def chargebee_create_subscription(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /subscriptions — create a subscription."""
    plan_id = config.get("plan_id") or input_data.get("plan_id")
    if not plan_id:
        raise ValueError("chargebee.create_subscription requires 'plan_id'")
    data: dict = {"plan_id": plan_id}
    for key in ("customer_id", "plan_quantity", "start_date", "trial_end",
                "billing_cycles", "coupon", "auto_collection"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            data[key] = v
    customer = config.get("customer") or input_data.get("customer")
    if customer and isinstance(customer, dict):
        for ck, cv in customer.items():
            data[f"customer[{ck}]"] = cv
    async with await _client(credential_id, db) as client:
        r = await client.post("/subscriptions", data=data)
    return _check(r)


@register_node("chargebee.cancel_subscription")
async def chargebee_cancel_subscription(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /subscriptions/{id}/cancel — cancel a subscription."""
    subscription_id = config.get("subscription_id") or input_data.get("subscription_id")
    if not subscription_id:
        raise ValueError("chargebee.cancel_subscription requires 'subscription_id'")
    data: dict = {}
    for key in ("end_of_term", "cancel_at_end", "credit_option_for_current_term_charges"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            data[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/subscriptions/{subscription_id}/cancel", data=data)
    return _check(r)


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------

@register_node("chargebee.list_customers")
async def chargebee_list_customers(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /customers — list customers."""
    params = {}
    for key in ("limit", "offset", "email[is]", "first_name[is]", "last_name[is]"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/customers", params=params)
    return _check(r)


@register_node("chargebee.get_customer")
async def chargebee_get_customer(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /customers/{id} — get a customer."""
    customer_id = config.get("customer_id") or input_data.get("customer_id")
    if not customer_id:
        raise ValueError("chargebee.get_customer requires 'customer_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/customers/{customer_id}")
    return _check(r)


@register_node("chargebee.create_customer")
async def chargebee_create_customer(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /customers — create a customer."""
    data: dict = {}
    for key in ("id", "first_name", "last_name", "email", "phone", "company",
                "locale", "taxability", "vat_number", "auto_collection"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            data[key] = v
    if not data.get("email") and not data.get("first_name"):
        raise ValueError("chargebee.create_customer requires at least 'email' or 'first_name'")
    billing_address = config.get("billing_address") or input_data.get("billing_address")
    if billing_address and isinstance(billing_address, dict):
        for bk, bv in billing_address.items():
            data[f"billing_address[{bk}]"] = bv
    async with await _client(credential_id, db) as client:
        r = await client.post("/customers", data=data)
    return _check(r)


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------

@register_node("chargebee.list_invoices")
async def chargebee_list_invoices(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /invoices — list invoices."""
    params = {}
    for key in ("limit", "offset", "status[is]", "customer_id[is]", "subscription_id[is]"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/invoices", params=params)
    return _check(r)


@register_node("chargebee.get_invoice")
async def chargebee_get_invoice(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /invoices/{id} — get an invoice."""
    invoice_id = config.get("invoice_id") or input_data.get("invoice_id")
    if not invoice_id:
        raise ValueError("chargebee.get_invoice requires 'invoice_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/invoices/{invoice_id}")
    return _check(r)


# ---------------------------------------------------------------------------
# Plans & Add-ons
# ---------------------------------------------------------------------------

@register_node("chargebee.list_plans")
async def chargebee_list_plans(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /plans — list plans."""
    params = {}
    for key in ("limit", "offset", "status[is]"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/plans", params=params)
    return _check(r)


@register_node("chargebee.list_addons")
async def chargebee_list_addons(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /addons — list add-ons."""
    params = {}
    for key in ("limit", "offset", "status[is]"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/addons", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Portal Sessions
# ---------------------------------------------------------------------------

@register_node("chargebee.create_portal_session")
async def chargebee_create_portal_session(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /portal_sessions — create a customer portal session."""
    customer_id = config.get("customer_id") or input_data.get("customer_id")
    if not customer_id:
        raise ValueError("chargebee.create_portal_session requires 'customer_id'")
    data: dict = {f"customer[id]": customer_id}
    redirect_url = config.get("redirect_url") or input_data.get("redirect_url")
    if redirect_url:
        data["redirect_url"] = redirect_url
    async with await _client(credential_id, db) as client:
        r = await client.post("/portal_sessions", data=data)
    return _check(r)
