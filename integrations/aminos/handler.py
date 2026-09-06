"""Aminos AI platform — handler for aminos integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.aminos.ai/v1"


@register_node("aminos.generate")
async def aminos_generate(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Generate content with AI.

    config/input_data:
      api_key — API key or token (required)
      prompt — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    prompt = merged.get("prompt") or ""
    if not prompt:
        raise ValueError("prompt required for aminos.generate")
    payload = {"prompt": prompt}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/generate", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("aminos.generate")
    return {"data": data}

@register_node("aminos.list_models")
async def aminos_list_models(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List available models.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/models", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("aminos.list_models")
    return {"data": data}
