"""HuggingFace Inference API integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

HF_BASE = "https://api-inference.huggingface.co/models"


@register_node("hugging_face.text_generation")
async def hugging_face_text_generation(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Generate text using a HuggingFace model.

    config/input_data:
      api_key — HuggingFace API token
      model   — model ID (e.g. "gpt2")
      prompt  — input text prompt
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    model = merged.get("model") or ""
    prompt = merged.get("prompt") or ""

    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {"inputs": prompt}

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{HF_BASE}/{model}", headers=headers, json=payload)
        r.raise_for_status()

    result = r.json()
    log.info("hugging_face.text_generation", model=model)
    return {"result": result}


@register_node("hugging_face.text_classification")
async def hugging_face_text_classification(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Classify text using a HuggingFace model.

    config/input_data:
      api_key — HuggingFace API token
      model   — model ID (e.g. "distilbert-base-uncased-finetuned-sst-2-english")
      text    — input text to classify
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    model = merged.get("model") or ""
    text = merged.get("text") or ""

    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {"inputs": text}

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{HF_BASE}/{model}", headers=headers, json=payload)
        r.raise_for_status()

    result = r.json()
    log.info("hugging_face.text_classification", model=model)
    return {"result": result}


@register_node("hugging_face.image_classification")
async def hugging_face_image_classification(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Classify an image using a HuggingFace model.

    config/input_data:
      api_key   — HuggingFace API token
      model     — model ID (e.g. "google/vit-base-patch16-224")
      file_path — local path to the image file
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    model = merged.get("model") or ""
    file_path = merged.get("file_path") or ""

    with open(file_path, "rb") as f:
        image_bytes = f.read()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/octet-stream",
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{HF_BASE}/{model}", headers=headers, content=image_bytes)
        r.raise_for_status()

    result = r.json()
    log.info("hugging_face.image_classification", model=model, file_path=file_path)
    return {"result": result}
