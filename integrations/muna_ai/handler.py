"""Muna AI content moderation — handler for muna_ai integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.muna.ai/v1"


@register_node("muna_ai.moderate_text")
async def muna_ai_moderate_text(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Moderate text content.

    config/input_data:
      api_key — API key or token (required)
      text — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    text = merged.get("text") or ""
    if not text:
        raise ValueError("text required for muna_ai.moderate_text")
    payload = merged
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/moderate/text", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("muna_ai.moderate_text")
    return {"data": data}

@register_node("muna_ai.moderate_image")
async def muna_ai_moderate_image(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Moderate image content.

    config/input_data:
      api_key — API key or token (required)
      image_url — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    image_url = merged.get("image_url") or ""
    if not image_url:
        raise ValueError("image_url required for muna_ai.moderate_image")
    payload = {"image_url": image_url}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/moderate/image", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("muna_ai.moderate_image")
    return {"data": data}
