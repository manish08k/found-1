"""PromoteKit — affiliate marketing integration."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

PROMOTEKIT_BASE = "https://promotekit.com/api/v1"


def _headers(config: dict) -> dict:
    api_key = config.get("api_key", "")
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


@register_node("promotekit.list_referrals")
async def promotekit_list_referrals(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List affiliate referrals from PromoteKit.

    config:
      api_key — PromoteKit API key
      limit   — number of referrals to return (default 25)
    """
    limit = int(config.get("limit", 25))

    async with httpx.AsyncClient(base_url=PROMOTEKIT_BASE, timeout=30) as client:
        r = await client.get("/referrals", params={"limit": limit}, headers=_headers(config))
        r.raise_for_status()
        data = r.json()

    referrals = data.get("data", data if isinstance(data, list) else [])
    log.info("promotekit.list_referrals", count=len(referrals))
    return {"referrals": referrals, "count": len(referrals)}


@register_node("promotekit.create_referral")
async def promotekit_create_referral(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create an affiliate referral in PromoteKit.

    config/input_data:
      api_key      — PromoteKit API key
      affiliate_id — affiliate user ID (required)
      customer_id  — referred customer ID (required)
    """
    affiliate_id = config.get("affiliate_id") or input_data.get("affiliate_id")
    customer_id = config.get("customer_id") or input_data.get("customer_id")

    if not affiliate_id:
        raise ValueError("affiliate_id is required for promotekit.create_referral")
    if not customer_id:
        raise ValueError("customer_id is required for promotekit.create_referral")

    async with httpx.AsyncClient(base_url=PROMOTEKIT_BASE, timeout=30) as client:
        r = await client.post(
            "/referrals",
            json={"affiliate_id": affiliate_id, "customer_id": customer_id},
            headers=_headers(config),
        )
        r.raise_for_status()
        referral = r.json()

    log.info("promotekit.create_referral", affiliate_id=affiliate_id, customer_id=customer_id)
    return {"referral": referral, "id": referral.get("id"), "affiliate_id": affiliate_id}
