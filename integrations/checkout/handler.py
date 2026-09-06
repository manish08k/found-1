"""Checkout.com payment processing — handler for checkout integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.checkout.com"


@register_node("checkout.create_payment")
async def checkout_create_payment(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a payment.

    config/input_data:
      api_key — API key or token (required)
      source — (required)
      amount — (required)
      currency — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    source = merged.get("source") or ""
    amount = merged.get("amount") or ""
    currency = merged.get("currency") or ""
    if not source or not amount or not currency:
        raise ValueError("source, amount, currency required for checkout.create_payment")
    payload = {"source": source, "amount": amount, "currency": currency}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/payments", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("checkout.create_payment")
    return {"data": data}

@register_node("checkout.get_payment")
async def checkout_get_payment(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get payment details.

    config/input_data:
      api_key — API key or token (required)
      payment_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payment_id = merged.get("payment_id") or ""
    if not payment_id:
        raise ValueError("payment_id required for checkout.get_payment")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/payments/{payment_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("checkout.get_payment")
    return {"data": data}

@register_node("checkout.capture_payment")
async def checkout_capture_payment(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Capture a payment.

    config/input_data:
      api_key — API key or token (required)
      payment_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payment_id = merged.get("payment_id") or ""
    if not payment_id:
        raise ValueError("payment_id required for checkout.capture_payment")
    payload = merged
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/payments/{payment_id}/captures", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("checkout.capture_payment")
    return {"data": data}

@register_node("checkout.refund_payment")
async def checkout_refund_payment(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Refund a payment.

    config/input_data:
      api_key — API key or token (required)
      payment_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payment_id = merged.get("payment_id") or ""
    if not payment_id:
        raise ValueError("payment_id required for checkout.refund_payment")
    payload = merged
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/payments/{payment_id}/refunds", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("checkout.refund_payment")
    return {"data": data}
