"""Runware AI image generation integration."""
import uuid
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

RUNWARE_BASE = "https://api.runware.ai/v1"


@register_node("runware.generate_image")
async def runware_generate_image(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Generate an image using Runware AI.

    config/input_data:
      api_key         — Runware API key
      prompt          — positive text prompt describing the image
      width           — image width in pixels (default 512)
      height          — image height in pixels (default 512)
      model           — model to use (default "runware:100@1")
      number_results  — number of images to generate (default 1)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    prompt = merged.get("prompt") or ""
    width = int(merged.get("width", 512))
    height = int(merged.get("height", 512))
    model = merged.get("model") or "runware:100@1"
    number_results = int(merged.get("number_results", 1))

    task_uuid = str(uuid.uuid4())
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = [
        {
            "taskType": "imageInference",
            "taskUUID": task_uuid,
            "positivePrompt": prompt,
            "width": width,
            "height": height,
            "model": model,
            "numberResults": number_results,
        }
    ]

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(RUNWARE_BASE, headers=headers, json=payload)
        r.raise_for_status()

    result = r.json()
    log.info("runware.generate_image", task_uuid=task_uuid, model=model)
    return {"result": result, "task_uuid": task_uuid}
