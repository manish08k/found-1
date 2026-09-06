"""Pinch Payments integration — customers, charges, and plans."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

PINCH_BASE = "https://api.pinchpayments.com"


def _pinch_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


@register_node("pinch_payments.create_customer")
async def pinch_create_customer(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new customer in Pinch Payments.

    config:
      api_key    — Pinch Payments API key (required)
      first_name — customer first name (required)
      last_name  — customer last name (required)
      email      — customer email address (required)
      phone      — customer phone number (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for pinch_payments.create_customer")

    payload = {k: v for k, v in {
        "first_name": merged.get("first_name"),
        "last_name": merged.get("last_name"),
        "email": merged.get("email"),
        "phone": merged.get("phone"),
    }.items() if v is not None}

    async with httpx.AsyncClient(base_url=PINCH_BASE, timeout=30) as client:
        r = await client.post("/api/customers", headers=_pinch_headers(api_key), json=payload)
        r.raise_for_status()
        customer = r.json()

    customer_id = customer.get("id")
    log.info("pinch_payments.create_customer", customer_id=customer_id)
    return {"customer": customer, "customer_id": customer_id}


@register_node("pinch_payments.list_customers")
async def pinch_list_customers(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List customers in Pinch Payments.

    config:
      api_key — Pinch Payments API key (required)
      page    — page number (optional, default 1)
      limit   — records per page (optional, default 25)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for pinch_payments.list_customers")

    params = {"page": merged.get("page", 1), "limit": merged.get("limit", 25)}

    async with httpx.AsyncClient(base_url=PINCH_BASE, timeout=30) as client:
        r = await client.get("/api/customers", headers=_pinch_headers(api_key), params=params)
        r.raise_for_status()
        data = r.json()

    customers = data.get("data", data) if isinstance(data, dict) else data
    log.info("pinch_payments.list_customers", count=len(customers) if isinstance(customers, list) else 1)
    return {"customers": customers, "meta": data.get("meta") if isinstance(data, dict) else None}


@register_node("pinch_payments.create_charge")
async def pinch_create_charge(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a charge (payment) in Pinch Payments.

    config:
      api_key     — Pinch Payments API key (required)
      customer_id — customer ID to charge (required)
      amount      — amount in cents (required)
      description — charge description (optional)
      reference   — external reference (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    customer_id = merged.get("customer_id")
    amount = merged.get("amount")
    if not api_key or not customer_id or amount is None:
        raise ValueError("api_key, customer_id, and amount are required")

    payload = {k: v for k, v in {
        "customer_id": customer_id,
        "amount": amount,
        "description": merged.get("description"),
        "reference": merged.get("reference"),
    }.items() if v is not None}

    async with httpx.AsyncClient(base_url=PINCH_BASE, timeout=30) as client:
        r = await client.post("/api/charges", headers=_pinch_headers(api_key), json=payload)
        r.raise_for_status()
        charge = r.json()

    charge_id = charge.get("id")
    log.info("pinch_payments.create_charge", charge_id=charge_id, amount=amount)
    return {"charge": charge, "charge_id": charge_id}


@register_node("pinch_payments.list_charges")
async def pinch_list_charges(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List charges in Pinch Payments.

    config:
      api_key     — Pinch Payments API key (required)
      customer_id — filter by customer ID (optional)
      page        — page number (optional, default 1)
      limit       — records per page (optional, default 25)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for pinch_payments.list_charges")

    params: dict = {"page": merged.get("page", 1), "limit": merged.get("limit", 25)}
    if merged.get("customer_id"):
        params["customer_id"] = merged["customer_id"]

    async with httpx.AsyncClient(base_url=PINCH_BASE, timeout=30) as client:
        r = await client.get("/api/charges", headers=_pinch_headers(api_key), params=params)
        r.raise_for_status()
        data = r.json()

    charges = data.get("data", data) if isinstance(data, dict) else data
    log.info("pinch_payments.list_charges", count=len(charges) if isinstance(charges, list) else 1)
    return {"charges": charges, "meta": data.get("meta") if isinstance(data, dict) else None}


@register_node("pinch_payments.create_plan")
async def pinch_create_plan(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a recurring billing plan in Pinch Payments.

    config:
      api_key       — Pinch Payments API key (required)
      name          — plan name (required)
      amount        — recurring amount in cents (required)
      frequency     — billing frequency: weekly/fortnightly/monthly/yearly (required)
      description   — plan description (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for pinch_payments.create_plan")

    payload = {k: v for k, v in {
        "name": merged.get("name"),
        "amount": merged.get("amount"),
        "frequency": merged.get("frequency"),
        "description": merged.get("description"),
    }.items() if v is not None}

    async with httpx.AsyncClient(base_url=PINCH_BASE, timeout=30) as client:
        r = await client.post("/api/plans", headers=_pinch_headers(api_key), json=payload)
        r.raise_for_status()
        plan = r.json()

    plan_id = plan.get("id")
    log.info("pinch_payments.create_plan", plan_id=plan_id)
    return {"plan": plan, "plan_id": plan_id}
