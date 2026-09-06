"""VLM Run vision language model API — handler for vlm_run integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.vlm.run/v1"


@register_node("vlm_run.analyze_image")
async def vlm_run_analyze_image(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Analyze an image with VLM.

    config/input_data:
      api_key — API key or token (required)
      image — (required)
      model — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    image = merged.get("image") or ""
    model = merged.get("model") or ""
    if not image or not model:
        raise ValueError("image, model required for vlm_run.analyze_image")
    payload = {"model": model}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/image/generate", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("vlm_run.analyze_image")
    return {"data": data}

@register_node("vlm_run.list_models")
async def vlm_run_list_models(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
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
    log.info("vlm_run.list_models")
    return {"data": data}
