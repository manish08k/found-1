"""Billplz integration — bills and collections (Malaysia)."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BILLPLZ_BASE = "https://www.billplz.com/api/v3"


@register_node("billplz.create_bill")
async def billplz_create_bill(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new Billplz bill.

    config/input_data:
      api_key       — Billplz API key (required, used as HTTP Basic username)
      collection_id — Collection ID (required)
      name          — Payer name (required)
      amount        — Amount in cents (required)
      callback_url  — Callback URL after payment (required)
      email         — Payer email (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    collection_id = config.get("collection_id") or input_data.get("collection_id")
    name = config.get("name") or input_data.get("name")
    amount = config.get("amount") or input_data.get("amount")
    callback_url = config.get("callback_url") or input_data.get("callback_url")
    email = config.get("email") or input_data.get("email")

    if not api_key:
        raise ValueError("api_key is required for billplz.create_bill")
    if not collection_id:
        raise ValueError("collection_id is required for billplz.create_bill")
    if not name:
        raise ValueError("name is required for billplz.create_bill")
    if not amount:
        raise ValueError("amount is required for billplz.create_bill")
    if not callback_url:
        raise ValueError("callback_url is required for billplz.create_bill")
    if not email:
        raise ValueError("email is required for billplz.create_bill")

    payload = {
        "collection_id": collection_id,
        "name": name,
        "amount": int(amount),
        "callback_url": callback_url,
        "email": email,
    }

    async with httpx.AsyncClient(base_url=BILLPLZ_BASE, timeout=30) as client:
        r = await client.post("/bills", auth=(api_key, ""), data=payload)
        r.raise_for_status()
        bill = r.json()

    log.info("billplz.create_bill", bill_id=bill.get("id"), state=bill.get("state"))
    return {"bill": bill, "id": bill.get("id"), "url": bill.get("url"), "state": bill.get("state")}


@register_node("billplz.get_bill")
async def billplz_get_bill(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a Billplz bill by ID.

    config/input_data:
      api_key — Billplz API key (required)
      bill_id — Bill ID (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    bill_id = config.get("bill_id") or input_data.get("bill_id")

    if not api_key:
        raise ValueError("api_key is required for billplz.get_bill")
    if not bill_id:
        raise ValueError("bill_id is required for billplz.get_bill")

    async with httpx.AsyncClient(base_url=BILLPLZ_BASE, timeout=30) as client:
        r = await client.get(f"/bills/{bill_id}", auth=(api_key, ""))
        r.raise_for_status()
        bill = r.json()

    log.info("billplz.get_bill", bill_id=bill_id, state=bill.get("state"))
    return {"bill": bill, "id": bill_id, "state": bill.get("state"), "paid": bill.get("paid")}


@register_node("billplz.list_collections")
async def billplz_list_collections(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Billplz collections.

    config:
      api_key — Billplz API key (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for billplz.list_collections")

    async with httpx.AsyncClient(base_url=BILLPLZ_BASE, timeout=30) as client:
        r = await client.get("/collections", auth=(api_key, ""))
        r.raise_for_status()
        data = r.json()

    collections = data.get("collections", data if isinstance(data, list) else [])
    log.info("billplz.list_collections", count=len(collections))
    return {"collections": collections, "count": len(collections)}
