"""Alltextify text extraction and conversion — handler for alltextify integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.alltextify.com/v1"


@register_node("alltextify.convert")
async def alltextify_convert(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Convert document to text.

    config/input_data:
      api_key — API key or token (required)
      file_url — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    file_url = merged.get("file_url") or ""
    if not file_url:
        raise ValueError("file_url required for alltextify.convert")
    payload = {"file_url": file_url}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/convert", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("alltextify.convert")
    return {"data": data}

@register_node("alltextify.get_result")
async def alltextify_get_result(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get conversion result.

    config/input_data:
      api_key — API key or token (required)
      job_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    job_id = merged.get("job_id") or ""
    if not job_id:
        raise ValueError("job_id required for alltextify.get_result")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/results/{job_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("alltextify.get_result")
    return {"data": data}
