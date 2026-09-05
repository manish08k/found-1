"""Eden AI aggregated AI APIs integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

EDEN_AI_BASE = "https://api.edenai.run/v2"


@register_node("eden_ai.text_generation")
async def eden_ai_text_generation(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Generate text using Eden AI.

    config/input_data:
      api_key    — Eden AI API key
      provider   — AI provider (e.g. "openai", "cohere")
      prompt     — text prompt
      temperature — sampling temperature (default 0.7)
      max_tokens — max tokens to generate (default 500)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    provider = merged.get("provider") or "openai"
    prompt = merged.get("prompt") or ""
    temperature = float(merged.get("temperature", 0.7))
    max_tokens = int(merged.get("max_tokens", 500))

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "providers": provider,
        "text": prompt,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{EDEN_AI_BASE}/text/generation", headers=headers, json=payload)
        r.raise_for_status()

    result = r.json()
    log.info("eden_ai.text_generation", provider=provider)
    return {"result": result}


@register_node("eden_ai.speech_to_text")
async def eden_ai_speech_to_text(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Transcribe speech to text using Eden AI.

    config/input_data:
      api_key   — Eden AI API key
      provider  — AI provider (e.g. "google", "amazon")
      language  — language code (default "en")
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    provider = merged.get("provider") or "google"
    language = merged.get("language") or "en"

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"providers": provider, "language": language}

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{EDEN_AI_BASE}/audio/speech_to_text_async", headers=headers, json=payload
        )
        r.raise_for_status()

    result = r.json()
    log.info("eden_ai.speech_to_text", provider=provider)
    return {"result": result}


@register_node("eden_ai.translation")
async def eden_ai_translation(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Translate text using Eden AI.

    config/input_data:
      api_key          — Eden AI API key
      provider         — AI provider (e.g. "google", "amazon")
      source_language  — source language code (e.g. "en")
      target_language  — target language code (e.g. "fr")
      text             — text to translate
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    provider = merged.get("provider") or "google"
    src = merged.get("source_language") or "en"
    tgt = merged.get("target_language") or "fr"
    text = merged.get("text") or ""

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "providers": provider,
        "source_language": src,
        "target_language": tgt,
        "text": text,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{EDEN_AI_BASE}/translation/automatic_translation", headers=headers, json=payload
        )
        r.raise_for_status()

    result = r.json()
    log.info("eden_ai.translation", provider=provider, src=src, tgt=tgt)
    return {"result": result}


@register_node("eden_ai.image_generation")
async def eden_ai_image_generation(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Generate images using Eden AI.

    config/input_data:
      api_key    — Eden AI API key
      provider   — AI provider (e.g. "openai", "stabilityai")
      prompt     — text prompt describing the image
      resolution — image resolution (default "512x512")
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    provider = merged.get("provider") or "openai"
    prompt = merged.get("prompt") or ""
    resolution = merged.get("resolution") or "512x512"

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"providers": provider, "text": prompt, "resolution": resolution}

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{EDEN_AI_BASE}/image/generation", headers=headers, json=payload)
        r.raise_for_status()

    result = r.json()
    log.info("eden_ai.image_generation", provider=provider)
    return {"result": result}
