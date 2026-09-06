"""Afforai AI-powered document analysis — handler for afforai integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.afforai.com/api"


@register_node("afforai.query")
async def afforai_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Query documents with AI.

    config/input_data:
      api_key — API key or token (required)
      query — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    query = merged.get("query") or ""
    if not query:
        raise ValueError("query required for afforai.query")
    payload = merged
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/query", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("afforai.query")
    return {"data": data}

@register_node("afforai.upload_document")
async def afforai_upload_document(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Upload a document for analysis.

    config/input_data:
      api_key — API key or token (required)
      file_url — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    file_url = merged.get("file_url") or ""
    if not file_url:
        raise ValueError("file_url required for afforai.upload_document")
    payload = {"file_url": file_url}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/upload", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("afforai.upload_document")
    return {"data": data}

@register_node("afforai.list_documents")
async def afforai_list_documents(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List uploaded documents.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/documents", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("afforai.list_documents")
    return {"data": data}
