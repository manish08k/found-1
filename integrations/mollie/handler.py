"""Mollie integration — payments and refunds."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

MOLLIE_BASE = "https://api.mollie.com/v2"


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


@register_node("mollie.list_payments")
async def mollie_list_payments(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List Mollie payments (up to 25).

    config:
      api_key — Mollie API key (required)
      limit   — number of payments to return (default 25, max 250)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for mollie.list_payments")
    limit = min(int(config.get("limit", 25)), 250)

    async with httpx.AsyncClient(base_url=MOLLIE_BASE, timeout=30) as client:
        r = await client.get("/payments", headers=_headers(api_key), params={"limit": limit})
        r.raise_for_status()
        data = r.json()

    payments = data.get("_embedded", {}).get("payments", [])
    log.info("mollie.list_payments", count=len(payments))
    return {"payments": payments, "count": len(payments), "links": data.get("_links", {})}


@register_node("mollie.create_payment")
async def mollie_create_payment(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new Mollie payment.

    config/input_data:
      api_key      — Mollie API key (required)
      currency     — ISO 4217 currency code (default "EUR")
      amount_str   — Amount as string e.g. "10.00" (required)
      description  — Payment description (required)
      redirect_url — URL to redirect after payment (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for mollie.create_payment")

    currency = config.get("currency") or input_data.get("currency", "EUR")
    amount_str = config.get("amount_str") or input_data.get("amount_str")
    description = config.get("description") or input_data.get("description")
    redirect_url = config.get("redirect_url") or input_data.get("redirect_url")

    if not amount_str:
        raise ValueError("amount_str is required for mollie.create_payment")
    if not description:
        raise ValueError("description is required for mollie.create_payment")
    if not redirect_url:
        raise ValueError("redirect_url is required for mollie.create_payment")

    payload = {
        "amount": {"currency": currency, "value": str(amount_str)},
        "description": description,
        "redirectUrl": redirect_url,
    }

    async with httpx.AsyncClient(base_url=MOLLIE_BASE, timeout=30) as client:
        r = await client.post("/payments", headers=_headers(api_key), json=payload)
        r.raise_for_status()
        payment = r.json()

    log.info("mollie.create_payment", payment_id=payment.get("id"), status=payment.get("status"))
    return {"payment": payment, "id": payment.get("id"), "status": payment.get("status"), "checkout_url": payment.get("_links", {}).get("checkout", {}).get("href")}


@register_node("mollie.get_payment")
async def mollie_get_payment(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single Mollie payment by ID.

    config/input_data:
      api_key — Mollie API key (required)
      id      — Payment ID (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    payment_id = config.get("id") or input_data.get("id")
    if not api_key:
        raise ValueError("api_key is required for mollie.get_payment")
    if not payment_id:
        raise ValueError("id is required for mollie.get_payment")

    async with httpx.AsyncClient(base_url=MOLLIE_BASE, timeout=30) as client:
        r = await client.get(f"/payments/{payment_id}", headers=_headers(api_key))
        r.raise_for_status()
        payment = r.json()

    log.info("mollie.get_payment", payment_id=payment_id, status=payment.get("status"))
    return {"payment": payment, "id": payment_id, "status": payment.get("status"), "amount": payment.get("amount")}


@register_node("mollie.list_refunds")
async def mollie_list_refunds(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List Mollie refunds.

    config:
      api_key — Mollie API key (required)
      limit   — number of refunds to return (default 25, max 250)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for mollie.list_refunds")
    limit = min(int(config.get("limit", 25)), 250)

    async with httpx.AsyncClient(base_url=MOLLIE_BASE, timeout=30) as client:
        r = await client.get("/refunds", headers=_headers(api_key), params={"limit": limit})
        r.raise_for_status()
        data = r.json()

    refunds = data.get("_embedded", {}).get("refunds", [])
    log.info("mollie.list_refunds", count=len(refunds))
    return {"refunds": refunds, "count": len(refunds), "links": data.get("_links", {})}
