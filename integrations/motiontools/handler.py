"""Motiontools delivery logistics platform — handler for motiontools integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.motiontools.com/v1"


@register_node("motiontools.create_delivery")
async def motiontools_create_delivery(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a delivery.

    config/input_data:
      api_key — API key or token (required)
      pickup — (required)
      dropoff — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    pickup = merged.get("pickup") or ""
    dropoff = merged.get("dropoff") or ""
    if not pickup or not dropoff:
        raise ValueError("pickup, dropoff required for motiontools.create_delivery")
    payload = {"pickup": pickup, "dropoff": dropoff}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/deliveries", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("motiontools.create_delivery")
    return {"data": data}

@register_node("motiontools.get_delivery")
async def motiontools_get_delivery(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get delivery status.

    config/input_data:
      api_key — API key or token (required)
      delivery_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    delivery_id = merged.get("delivery_id") or ""
    if not delivery_id:
        raise ValueError("delivery_id required for motiontools.get_delivery")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/deliveries/{delivery_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("motiontools.get_delivery")
    return {"data": data}

@register_node("motiontools.list_deliveries")
async def motiontools_list_deliveries(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List deliveries.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/deliveries", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("motiontools.list_deliveries")
    return {"data": data}
