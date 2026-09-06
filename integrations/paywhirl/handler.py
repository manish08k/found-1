"""Paywhirl integration — plans, customers, and subscriptions."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

PAYWHIRL_BASE = "https://api.paywhirl.com"


def _paywhirl_headers(api_key: str, api_secret: str) -> dict:
    return {
        "api-key": api_key,
        "api-secret": api_secret,
        "Content-Type": "application/json",
    }


@register_node("paywhirl.list_plans")
async def paywhirl_list_plans(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all subscription plans in Paywhirl.

    config:
      api_key    — Paywhirl API key (required)
      api_secret — Paywhirl API secret (required)
      limit      — number of plans to return (optional, default 100)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    api_secret = merged.get("api_secret", "")
    if not api_key or not api_secret:
        raise ValueError("api_key and api_secret are required for paywhirl.list_plans")

    params = {"limit": merged.get("limit", 100)}

    async with httpx.AsyncClient(base_url=PAYWHIRL_BASE, timeout=30) as client:
        r = await client.get("/plans", headers=_paywhirl_headers(api_key, api_secret), params=params)
        r.raise_for_status()
        plans = r.json()

    log.info("paywhirl.list_plans", count=len(plans) if isinstance(plans, list) else 1)
    return {"plans": plans}


@register_node("paywhirl.get_plan")
async def paywhirl_get_plan(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a specific Paywhirl plan by ID.

    config:
      api_key    — Paywhirl API key (required)
      api_secret — Paywhirl API secret (required)
      plan_id    — plan ID to retrieve (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    api_secret = merged.get("api_secret", "")
    plan_id = merged.get("plan_id")
    if not api_key or not api_secret or not plan_id:
        raise ValueError("api_key, api_secret, and plan_id are required")

    async with httpx.AsyncClient(base_url=PAYWHIRL_BASE, timeout=30) as client:
        r = await client.get(f"/plan/{plan_id}", headers=_paywhirl_headers(api_key, api_secret))
        r.raise_for_status()
        plan = r.json()

    log.info("paywhirl.get_plan", plan_id=plan_id)
    return {"plan": plan, "plan_id": plan_id}


@register_node("paywhirl.list_customers")
async def paywhirl_list_customers(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List customers in Paywhirl.

    config:
      api_key    — Paywhirl API key (required)
      api_secret — Paywhirl API secret (required)
      limit      — number of customers to return (optional, default 100)
      starting_after — pagination cursor (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    api_secret = merged.get("api_secret", "")
    if not api_key or not api_secret:
        raise ValueError("api_key and api_secret are required")

    params: dict = {"limit": merged.get("limit", 100)}
    if merged.get("starting_after"):
        params["starting_after"] = merged["starting_after"]

    async with httpx.AsyncClient(base_url=PAYWHIRL_BASE, timeout=30) as client:
        r = await client.get("/customers", headers=_paywhirl_headers(api_key, api_secret), params=params)
        r.raise_for_status()
        customers = r.json()

    log.info("paywhirl.list_customers", count=len(customers) if isinstance(customers, list) else 1)
    return {"customers": customers}


@register_node("paywhirl.get_customer")
async def paywhirl_get_customer(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a specific Paywhirl customer by ID.

    config:
      api_key     — Paywhirl API key (required)
      api_secret  — Paywhirl API secret (required)
      customer_id — customer ID to retrieve (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    api_secret = merged.get("api_secret", "")
    customer_id = merged.get("customer_id")
    if not api_key or not api_secret or not customer_id:
        raise ValueError("api_key, api_secret, and customer_id are required")

    async with httpx.AsyncClient(base_url=PAYWHIRL_BASE, timeout=30) as client:
        r = await client.get(f"/customer/{customer_id}", headers=_paywhirl_headers(api_key, api_secret))
        r.raise_for_status()
        customer = r.json()

    log.info("paywhirl.get_customer", customer_id=customer_id)
    return {"customer": customer, "customer_id": customer_id}


@register_node("paywhirl.create_subscription")
async def paywhirl_create_subscription(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a subscription for a customer in Paywhirl.

    config:
      api_key     — Paywhirl API key (required)
      api_secret  — Paywhirl API secret (required)
      customer_id — customer ID (required)
      plan_id     — plan ID to subscribe to (required)
      gateway_id  — payment gateway ID (optional)
      quantity    — subscription quantity (optional, default 1)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    api_secret = merged.get("api_secret", "")
    customer_id = merged.get("customer_id")
    plan_id = merged.get("plan_id")
    if not api_key or not api_secret or not customer_id or not plan_id:
        raise ValueError("api_key, api_secret, customer_id, and plan_id are required")

    payload: dict = {
        "customer_id": customer_id,
        "plan_id": plan_id,
        "quantity": merged.get("quantity", 1),
    }
    if merged.get("gateway_id"):
        payload["gateway_id"] = merged["gateway_id"]

    async with httpx.AsyncClient(base_url=PAYWHIRL_BASE, timeout=30) as client:
        r = await client.post("/subscribe", headers=_paywhirl_headers(api_key, api_secret), json=payload)
        r.raise_for_status()
        subscription = r.json()

    subscription_id = subscription.get("id")
    log.info("paywhirl.create_subscription", subscription_id=subscription_id, customer_id=customer_id)
    return {"subscription": subscription, "subscription_id": subscription_id}


@register_node("paywhirl.cancel_subscription")
async def paywhirl_cancel_subscription(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Cancel an active subscription in Paywhirl.

    config:
      api_key         — Paywhirl API key (required)
      api_secret      — Paywhirl API secret (required)
      subscription_id — subscription ID to cancel (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    api_secret = merged.get("api_secret", "")
    subscription_id = merged.get("subscription_id")
    if not api_key or not api_secret or not subscription_id:
        raise ValueError("api_key, api_secret, and subscription_id are required")

    payload = {"subscription_id": subscription_id}

    async with httpx.AsyncClient(base_url=PAYWHIRL_BASE, timeout=30) as client:
        r = await client.post("/unsubscribe", headers=_paywhirl_headers(api_key, api_secret), json=payload)
        r.raise_for_status()
        result = r.json()

    log.info("paywhirl.cancel_subscription", subscription_id=subscription_id)
    return {"result": result, "subscription_id": subscription_id}
