"""Al AI document processing — handler for alai integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.al.ai/v1"


@register_node("alai.extract")
async def alai_extract(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Extract data from document.

    config/input_data:
      api_key — API key or token (required)
      document_url — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    document_url = merged.get("document_url") or ""
    if not document_url:
        raise ValueError("document_url required for alai.extract")
    payload = {"document_url": document_url}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/extract", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("alai.extract")
    return {"data": data}

@register_node("alai.list_extractions")
async def alai_list_extractions(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List extractions.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/extractions", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("alai.list_extractions")
    return {"data": data}

@register_node("alai.get_extraction")
async def alai_get_extraction(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get extraction result.

    config/input_data:
      api_key — API key or token (required)
      extraction_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    extraction_id = merged.get("extraction_id") or ""
    if not extraction_id:
        raise ValueError("extraction_id required for alai.get_extraction")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/extractions/{extraction_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("alai.get_extraction")
    return {"data": data}
