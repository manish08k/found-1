"""Luxury Presence real estate marketing — handler for luxury_presence integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.luxurypresence.com/v1"


@register_node("luxury_presence.list_listings")
async def luxury_presence_list_listings(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List property listings.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/listings", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("luxury_presence.list_listings")
    return {"data": data}

@register_node("luxury_presence.get_listing")
async def luxury_presence_get_listing(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get listing details.

    config/input_data:
      api_key — API key or token (required)
      listing_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    listing_id = merged.get("listing_id") or ""
    if not listing_id:
        raise ValueError("listing_id required for luxury_presence.get_listing")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/listings/{listing_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("luxury_presence.get_listing")
    return {"data": data}

@register_node("luxury_presence.list_leads")
async def luxury_presence_list_leads(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List leads.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/leads", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("luxury_presence.list_leads")
    return {"data": data}
