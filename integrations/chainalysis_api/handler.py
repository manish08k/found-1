"""Chainalysis blockchain compliance and analytics — handler for chainalysis_api integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.chainalysis.com/api/kyt/v2"


@register_node("chainalysis_api.register_transfer")
async def chainalysis_api_register_transfer(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Register a transfer for screening.

    config/input_data:
      api_key — API key or token (required)
      user_id — (required)
      network — (required)
      asset — (required)
      transferReference — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Token": api_key, "Content-Type": "application/json"}
    user_id = merged.get("user_id") or ""
    network = merged.get("network") or ""
    asset = merged.get("asset") or ""
    transferReference = merged.get("transferReference") or ""
    if not user_id or not network or not asset or not transferReference:
        raise ValueError("user_id, network, asset, transferReference required for chainalysis_api.register_transfer")
    payload = {"network": network, "asset": asset, "transferReference": transferReference}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/users/{user_id}/transfers", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("chainalysis_api.register_transfer")
    return {"data": data}

@register_node("chainalysis_api.get_transfer")
async def chainalysis_api_get_transfer(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get transfer screening results.

    config/input_data:
      api_key — API key or token (required)
      external_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Token": api_key, "Content-Type": "application/json"}
    external_id = merged.get("external_id") or ""
    if not external_id:
        raise ValueError("external_id required for chainalysis_api.get_transfer")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/transfers/{external_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("chainalysis_api.get_transfer")
    return {"data": data}
