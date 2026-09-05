"""ChargeKeeper subscription management integration — subscriptions."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

CHARGEKEEPER_BASE = "https://chargekeeper.com/api/v1"


@register_node("chargekeeper.list_subscriptions")
async def chargekeeper_list_subscriptions(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List subscriptions from ChargeKeeper.

    config/input_data:
      api_key — ChargeKeeper API key (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{CHARGEKEEPER_BASE}/subscriptions"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()

    subscriptions = data.get("data", data) if isinstance(data, dict) else data
    log.info("chargekeeper.list_subscriptions", count=len(subscriptions) if isinstance(subscriptions, list) else None)
    return {"subscriptions": subscriptions}


@register_node("chargekeeper.get_subscription")
async def chargekeeper_get_subscription(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single subscription from ChargeKeeper by ID.

    config/input_data:
      api_key — ChargeKeeper API key (required)
      id      — subscription ID (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    subscription_id = merged.get("id") or merged.get("subscription_id") or ""

    if not subscription_id:
        raise ValueError("id is required for chargekeeper.get_subscription")

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{CHARGEKEEPER_BASE}/subscriptions/{subscription_id}"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()

    subscription = data.get("data", data) if isinstance(data, dict) else data
    log.info("chargekeeper.get_subscription", id=subscription_id)
    return {"subscription": subscription}
