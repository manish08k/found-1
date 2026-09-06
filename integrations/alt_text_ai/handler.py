"""Alt Text AI — automatic alt text generation for images — handler for alt_text_ai integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://alttext.ai/api/v1"


@register_node("alt_text_ai.generate_alt_text")
async def alt_text_ai_generate_alt_text(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Generate alt text for an image.

    config/input_data:
      api_key — API key or token (required)
      image_url — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    image_url = merged.get("image_url") or ""
    if not image_url:
        raise ValueError("image_url required for alt_text_ai.generate_alt_text")
    payload = {"image_url": image_url}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/images", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("alt_text_ai.generate_alt_text")
    return {"data": data}

@register_node("alt_text_ai.get_alt_text")
async def alt_text_ai_get_alt_text(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get generated alt text.

    config/input_data:
      api_key — API key or token (required)
      image_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    image_id = merged.get("image_id") or ""
    if not image_id:
        raise ValueError("image_id required for alt_text_ai.get_alt_text")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/images/{image_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("alt_text_ai.get_alt_text")
    return {"data": data}

@register_node("alt_text_ai.list_images")
async def alt_text_ai_list_images(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List processed images.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/images", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("alt_text_ai.list_images")
    return {"data": data}
