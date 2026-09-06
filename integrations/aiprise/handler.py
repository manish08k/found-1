"""AIPrise identity verification — handler for aiprise integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.aiprise.com/v1"


@register_node("aiprise.verify_identity")
async def aiprise_verify_identity(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Verify user identity.

    config/input_data:
      api_key — API key or token (required)
      document_url — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    document_url = merged.get("document_url") or ""
    if not document_url:
        raise ValueError("document_url required for aiprise.verify_identity")
    payload = {"document_url": document_url}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/verify", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("aiprise.verify_identity")
    return {"data": data}

@register_node("aiprise.get_verification")
async def aiprise_get_verification(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get verification result.

    config/input_data:
      api_key — API key or token (required)
      verification_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    verification_id = merged.get("verification_id") or ""
    if not verification_id:
        raise ValueError("verification_id required for aiprise.get_verification")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/verifications/{verification_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("aiprise.get_verification")
    return {"data": data}

@register_node("aiprise.list_verifications")
async def aiprise_list_verifications(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all verifications.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/verifications", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("aiprise.list_verifications")
    return {"data": data}
