"""
Stripe integration — payments/billing automation.

Uses Stripe's REST API directly via httpx rather than the official
`stripe` Python SDK, to avoid adding a heavyweight dependency for what's
a handful of simple Bearer-authenticated REST calls. Credential is a
single field: the Stripe secret key (test or live — the user chooses
which by which key they paste in), stored the same way a database
password is (envelope encryption, credentials/envelope.py).
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

STRIPE_BASE = "https://api.stripe.com/v1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key") or creds.get("secret_key")
    if not api_key:
        raise ValueError("Stripe credential is missing 'api_key'")
    return httpx.AsyncClient(
        base_url=STRIPE_BASE,
        auth=(api_key, ""),  # Stripe uses HTTP Basic auth with the secret key as username, empty password
        timeout=30,
    )


@register_node("stripe.create_payment_link")
async def stripe_create_payment_link(config: dict, input_data: dict, credential_id: str, db) -> dict:
    price_id = config.get("price_id") or input_data.get("price_id")
    quantity = int(config.get("quantity", input_data.get("quantity", 1)))
    if not price_id:
        raise ValueError("stripe.create_payment_link requires 'price_id'")

    async with await _client(credential_id, db) as client:
        r = await client.post("/payment_links", data={
            "line_items[0][price]": price_id,
            "line_items[0][quantity]": quantity,
        })
        r.raise_for_status()
        data = r.json()
    return {"id": data["id"], "url": data["url"]}


@register_node("stripe.get_customer")
async def stripe_get_customer(config: dict, input_data: dict, credential_id: str, db) -> dict:
    customer_id = config.get("customer_id") or input_data.get("customer_id")
    if not customer_id:
        raise ValueError("stripe.get_customer requires 'customer_id'")

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/customers/{customer_id}")
        r.raise_for_status()
        data = r.json()
    return {
        "id": data["id"], "email": data.get("email"), "name": data.get("name"),
        "balance": data.get("balance"), "currency": data.get("currency"),
    }


@register_node("stripe.list_charges")
async def stripe_list_charges(config: dict, input_data: dict, credential_id: str, db) -> dict:
    customer_id = config.get("customer_id") or input_data.get("customer_id")
    limit = min(int(config.get("limit", 10)), 100)
    params = {"limit": limit}
    if customer_id:
        params["customer"] = customer_id

    async with await _client(credential_id, db) as client:
        r = await client.get("/charges", params=params)
        r.raise_for_status()
        data = r.json()
    return {
        "charges": [
            {"id": c["id"], "amount": c["amount"], "currency": c["currency"], "status": c["status"], "paid": c["paid"]}
            for c in data.get("data", [])
        ],
        "has_more": data.get("has_more", False),
    }


@register_node("stripe.create_refund")
async def stripe_create_refund(config: dict, input_data: dict, credential_id: str, db) -> dict:
    charge_id = config.get("charge_id") or input_data.get("charge_id")
    amount = config.get("amount") or input_data.get("amount")  # cents; omit for a full refund
    if not charge_id:
        raise ValueError("stripe.create_refund requires 'charge_id'")

    payload = {"charge": charge_id}
    if amount:
        payload["amount"] = int(amount)

    async with await _client(credential_id, db) as client:
        r = await client.post("/refunds", data=payload)
        r.raise_for_status()
        data = r.json()
    return {"id": data["id"], "status": data["status"], "amount": data["amount"]}


async def test_connection(creds: dict) -> None:
    """Used by POST /credentials/{id}/test — confirms the key is valid without side effects."""
    api_key = creds.get("api_key") or creds.get("secret_key")
    if not api_key:
        raise ValueError("Missing api_key")
    async with httpx.AsyncClient(base_url=STRIPE_BASE, auth=(api_key, ""), timeout=10) as client:
        r = await client.get("/balance")
        r.raise_for_status()
