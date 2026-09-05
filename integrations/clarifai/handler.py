"""Clarifai AI visual recognition integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

CLARIFAI_BASE = "https://api.clarifai.com/v2"


@register_node("clarifai.predict_image")
async def clarifai_predict_image(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Run image prediction using a Clarifai model.

    config/input_data:
      api_key    — Clarifai API key
      model_id   — Clarifai model ID
      version_id — model version ID
      image_url  — URL of the image to analyze
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    model_id = merged.get("model_id") or ""
    version_id = merged.get("version_id") or ""
    image_url = merged.get("image_url") or ""

    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "inputs": [{"data": {"image": {"url": image_url}}}]
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{CLARIFAI_BASE}/models/{model_id}/versions/{version_id}/outputs",
            headers=headers,
            json=payload,
        )
        r.raise_for_status()

    result = r.json()
    log.info("clarifai.predict_image", model_id=model_id)
    return {"result": result}


@register_node("clarifai.predict_text")
async def clarifai_predict_text(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Run text prediction using a Clarifai model.

    config/input_data:
      api_key    — Clarifai API key
      model_id   — Clarifai model ID
      version_id — model version ID
      text       — text to analyze
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    model_id = merged.get("model_id") or ""
    version_id = merged.get("version_id") or ""
    text = merged.get("text") or ""

    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "inputs": [{"data": {"text": {"raw": text}}}]
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{CLARIFAI_BASE}/models/{model_id}/versions/{version_id}/outputs",
            headers=headers,
            json=payload,
        )
        r.raise_for_status()

    result = r.json()
    log.info("clarifai.predict_text", model_id=model_id)
    return {"result": result}
