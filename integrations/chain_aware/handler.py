"""ChainAware blockchain analytics — handler for chain_aware integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.chainaware.ai/v1"


@register_node("chain_aware.analyze_address")
async def chain_aware_analyze_address(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Analyze a blockchain address.

    config/input_data:
      api_key — API key or token (required)
      address — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    address = merged.get("address") or ""
    if not address:
        raise ValueError("address required for chain_aware.analyze_address")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/address/{address}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("chain_aware.analyze_address")
    return {"data": data}

@register_node("chain_aware.get_risk_score")
async def chain_aware_get_risk_score(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get address risk score.

    config/input_data:
      api_key — API key or token (required)
      address — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    address = merged.get("address") or ""
    if not address:
        raise ValueError("address required for chain_aware.get_risk_score")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/risk/{address}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("chain_aware.get_risk_score")
    return {"data": data}
