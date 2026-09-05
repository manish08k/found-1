"""Runway ML generative video integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

RUNWAY_BASE = "https://api.dev.runwayml.com/v1"


@register_node("runway.generate_video")
async def runway_generate_video(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Generate a video from an image using Runway ML.

    config/input_data:
      api_key   — Runway ML API key
      image_url — URL of the source image
      text      — text prompt to guide the generation
      model     — model to use (default "gen3a_turbo")
      duration  — video duration in seconds (default 5)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    image_url = merged.get("image_url") or ""
    text = merged.get("text") or ""
    model = merged.get("model") or "gen3a_turbo"
    duration = int(merged.get("duration", 5))

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "promptImage": image_url,
        "promptText": text,
        "model": model,
        "duration": duration,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{RUNWAY_BASE}/image_to_video", headers=headers, json=payload)
        r.raise_for_status()

    result = r.json()
    log.info("runway.generate_video", task_id=result.get("id"))
    return {"result": result}


@register_node("runway.get_task")
async def runway_get_task(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get the status of a Runway ML generation task.

    config/input_data:
      api_key — Runway ML API key
      task_id — ID of the task to retrieve
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    task_id = merged.get("task_id") or ""

    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{RUNWAY_BASE}/tasks/{task_id}", headers=headers)
        r.raise_for_status()

    result = r.json()
    log.info("runway.get_task", task_id=task_id, status=result.get("status"))
    return {"result": result}
