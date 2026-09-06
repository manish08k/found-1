"""XQuik data processing platform — handler for xquik integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.xquik.com/v1"


@register_node("xquik.process")
async def xquik_process(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Process data.

    config/input_data:
      api_key — API key or token (required)
      data — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = merged.get("data") or ""
    if not data:
        raise ValueError("data required for xquik.process")
    payload = {"data": data}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/process", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("xquik.process")
    return {"data": data}

@register_node("xquik.get_result")
async def xquik_get_result(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get processing result.

    config/input_data:
      api_key — API key or token (required)
      job_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    job_id = merged.get("job_id") or ""
    if not job_id:
        raise ValueError("job_id required for xquik.get_result")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/results/{job_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("xquik.get_result")
    return {"data": data}
