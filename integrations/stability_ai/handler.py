"""Stability AI image generation integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

STABILITY_BASE = "https://api.stability.ai/v1"


@register_node("stability_ai.generate_image")
async def stability_ai_generate_image(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Generate an image from text using Stability AI.

    config/input_data:
      api_key   — Stability AI API key
      engine_id — engine to use (default "stable-diffusion-v1-6")
      prompt    — text prompt describing the image
      cfg_scale — classifier-free guidance scale (default 7)
      height    — image height in pixels (default 512)
      width     — image width in pixels (default 512)
      steps     — number of diffusion steps (default 30)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    engine_id = merged.get("engine_id") or "stable-diffusion-v1-6"
    prompt = merged.get("prompt") or ""
    cfg_scale = float(merged.get("cfg_scale", 7))
    height = int(merged.get("height", 512))
    width = int(merged.get("width", 512))
    steps = int(merged.get("steps", 30))

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "text_prompts": [{"text": prompt}],
        "cfg_scale": cfg_scale,
        "height": height,
        "width": width,
        "steps": steps,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{STABILITY_BASE}/generation/{engine_id}/text-to-image",
            headers=headers,
            json=payload,
        )
        r.raise_for_status()

    data = r.json()
    artifacts = data.get("artifacts", [])
    log.info("stability_ai.generate_image", engine_id=engine_id, artifact_count=len(artifacts))
    return {"result": data, "artifacts": artifacts}


@register_node("stability_ai.list_engines")
async def stability_ai_list_engines(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List available Stability AI engines.

    config/input_data:
      api_key — Stability AI API key
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""

    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{STABILITY_BASE}/engines/list", headers=headers)
        r.raise_for_status()

    result = r.json()
    log.info("stability_ai.list_engines", count=len(result) if isinstance(result, list) else 0)
    return {"result": result}
