"""Talkable — referral marketing integration."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

TALKABLE_BASE = "https://www.talkable.com/api/v2"


def _headers(config: dict) -> dict:
    api_key = config.get("api_key", "")
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


@register_node("talkable.list_campaigns")
async def talkable_list_campaigns(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List referral campaigns from Talkable.

    config:
      api_key  — Talkable API key
      per_page — number of campaigns per page (default 25)
    """
    per_page = int(config.get("per_page", 25))

    async with httpx.AsyncClient(base_url=TALKABLE_BASE, timeout=30) as client:
        r = await client.get(
            "/campaigns",
            params={"per_page": per_page},
            headers=_headers(config),
        )
        r.raise_for_status()
        data = r.json()

    campaigns = data.get("campaigns", data if isinstance(data, list) else [])
    log.info("talkable.list_campaigns", count=len(campaigns))
    return {"campaigns": campaigns, "count": len(campaigns)}


@register_node("talkable.get_referrals")
async def talkable_get_referrals(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get referrals from Talkable.

    config:
      api_key  — Talkable API key
      per_page — number of referrals per page (default 25)
    """
    per_page = int(config.get("per_page", 25))

    async with httpx.AsyncClient(base_url=TALKABLE_BASE, timeout=30) as client:
        r = await client.get(
            "/referrals",
            params={"per_page": per_page},
            headers=_headers(config),
        )
        r.raise_for_status()
        data = r.json()

    referrals = data.get("referrals", data if isinstance(data, list) else [])
    log.info("talkable.get_referrals", count=len(referrals))
    return {"referrals": referrals, "count": len(referrals)}


@register_node("talkable.create_purchase")
async def talkable_create_purchase(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Report a purchase event to Talkable for referral attribution.

    config/input_data:
      api_key      — Talkable API key
      site_slug    — Talkable site slug (required)
      email        — customer email address (required)
      order_id     — order number/ID (required)
      amount       — order subtotal amount (required)
    """
    site_slug = config.get("site_slug") or input_data.get("site_slug")
    email = config.get("email") or input_data.get("email")
    order_id = config.get("order_id") or input_data.get("order_id")
    amount = config.get("amount") or input_data.get("amount")

    if not site_slug:
        raise ValueError("site_slug is required for talkable.create_purchase")
    if not email:
        raise ValueError("email is required for talkable.create_purchase")
    if not order_id:
        raise ValueError("order_id is required for talkable.create_purchase")
    if amount is None:
        raise ValueError("amount is required for talkable.create_purchase")

    payload = {
        "site_slug": site_slug,
        "data": {
            "email": email,
            "order_number": order_id,
            "subtotal": amount,
        },
    }

    async with httpx.AsyncClient(base_url=TALKABLE_BASE, timeout=30) as client:
        r = await client.post("/purchases", json=payload, headers=_headers(config))
        r.raise_for_status()
        result = r.json()

    log.info("talkable.create_purchase", site_slug=site_slug, order_id=order_id, email=email)
    return {"purchase": result, "order_id": order_id, "email": email}
