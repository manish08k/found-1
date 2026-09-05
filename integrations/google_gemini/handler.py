"""Google Gemini generative AI integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"


@register_node("google_gemini.generate_content")
async def google_gemini_generate_content(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Generate content using Google Gemini.

    config/input_data:
      api_key  — Google AI Studio API key
      model    — model ID (default "gemini-1.5-flash")
      contents — list of content objects (e.g. [{"parts": [{"text": "..."}]}])
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    model = merged.get("model") or "gemini-1.5-flash"
    contents = merged.get("contents") or []

    payload = {"contents": contents}
    url = f"{GEMINI_BASE}/models/{model}:generateContent"

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, json=payload, params={"key": api_key})
        r.raise_for_status()

    data = r.json()
    candidate = data.get("candidates", [{}])[0].get("content", {})
    log.info("google_gemini.generate_content", model=model)
    return {"result": data, "content": candidate}


@register_node("google_gemini.list_models")
async def google_gemini_list_models(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List available Google Gemini models.

    config/input_data:
      api_key — Google AI Studio API key
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{GEMINI_BASE}/models", params={"key": api_key})
        r.raise_for_status()

    result = r.json()
    log.info("google_gemini.list_models", count=len(result.get("models", [])))
    return {"result": result}
