"""ModelsLab Stable Diffusion API integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

MODELSLAB_BASE = "https://modelslab.com/api/v6"


@register_node("modelslab.text_to_image")
async def modelslab_text_to_image(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Generate an image from text using ModelsLab.

    config/input_data:
      api_key       — ModelsLab API key
      prompt        — text prompt describing the image
      width         — image width in pixels (default "512")
      height        — image height in pixels (default "512")
      negative_prompt — optional negative prompt
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    prompt = merged.get("prompt") or ""
    width = str(merged.get("width", "512"))
    height = str(merged.get("height", "512"))
    negative_prompt = merged.get("negative_prompt") or ""

    payload: dict = {
        "key": api_key,
        "prompt": prompt,
        "width": width,
        "height": height,
    }
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{MODELSLAB_BASE}/images/text2img", json=payload)
        r.raise_for_status()

    result = r.json()
    log.info("modelslab.text_to_image", status=result.get("status"))
    return {"result": result}


@register_node("modelslab.image_to_image")
async def modelslab_image_to_image(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Transform an image using ModelsLab img2img.

    config/input_data:
      api_key       — ModelsLab API key
      prompt        — text prompt describing the transformation
      init_image    — URL of the source image
      width         — output width in pixels (default "512")
      height        — output height in pixels (default "512")
      strength      — transformation strength 0.0-1.0 (default 0.7)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    prompt = merged.get("prompt") or ""
    init_image = merged.get("init_image") or ""
    width = str(merged.get("width", "512"))
    height = str(merged.get("height", "512"))
    strength = float(merged.get("strength", 0.7))

    payload = {
        "key": api_key,
        "prompt": prompt,
        "init_image": init_image,
        "width": width,
        "height": height,
        "strength": strength,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{MODELSLAB_BASE}/images/img2img", json=payload)
        r.raise_for_status()

    result = r.json()
    log.info("modelslab.image_to_image", status=result.get("status"))
    return {"result": result}
