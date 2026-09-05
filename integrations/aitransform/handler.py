"""
AiTransform data transformation with AI integration.

Provides text transformation, classification, and entity extraction
via the AiTransform API v1.

Credential fields:
  - api_key : AiTransform API key

Auth: Bearer token.
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://api.aitransform.io/v1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("AiTransform credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=60.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"AiTransform API error {r.status_code}: {detail}")


@register_node("aitransform.transform_text")
async def ait_transform_text(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Transform text according to a specified instruction or template."""
    text = config.get("text") or input_data.get("text")
    instruction = config.get("instruction") or input_data.get("instruction")

    if not text:
        raise ValueError("aitransform.transform_text requires 'text'")
    if not instruction:
        raise ValueError("aitransform.transform_text requires 'instruction' describing the transformation")

    # Optional parameters
    model = config.get("model") or input_data.get("model", "default")
    output_format = config.get("output_format") or input_data.get("output_format", "text")
    language = config.get("language") or input_data.get("language")
    max_length = config.get("max_length") or input_data.get("max_length")

    payload: dict = {
        "text": text,
        "instruction": instruction,
        "model": model,
        "output_format": output_format,
    }
    if language:
        payload["language"] = language
    if max_length:
        payload["max_length"] = int(max_length)

    async with await _client(credential_id, db) as client:
        r = await client.post("/transform", json=payload)
        _raise_for_status(r)
        data = r.json()

    result = data.get("result") or data.get("transformed_text", "")
    log.info("aitransform.transform_text", input_length=len(text), output_length=len(str(result)))
    return {
        "result": result,
        "original_text": text,
        "instruction": instruction,
        "usage": data.get("usage", {}),
    }


@register_node("aitransform.classify_text")
async def ait_classify_text(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Classify text into one or more predefined categories."""
    text = config.get("text") or input_data.get("text")
    categories = config.get("categories") or input_data.get("categories")

    if not text:
        raise ValueError("aitransform.classify_text requires 'text'")
    if not categories:
        raise ValueError("aitransform.classify_text requires 'categories' (list of strings)")

    # Normalize categories to a list
    if isinstance(categories, str):
        categories = [c.strip() for c in categories.split(",") if c.strip()]

    multi_label = config.get("multi_label") if "multi_label" in config else input_data.get("multi_label", False)
    model = config.get("model") or input_data.get("model", "default")
    confidence_threshold = config.get("confidence_threshold") or input_data.get("confidence_threshold")

    payload: dict = {
        "text": text,
        "categories": categories,
        "multi_label": bool(multi_label),
        "model": model,
    }
    if confidence_threshold is not None:
        payload["confidence_threshold"] = float(confidence_threshold)

    async with await _client(credential_id, db) as client:
        r = await client.post("/classify", json=payload)
        _raise_for_status(r)
        data = r.json()

    predicted = data.get("predicted_class") or data.get("classification", "")
    scores = data.get("scores") or data.get("probabilities", {})
    log.info("aitransform.classify_text", predicted=predicted)
    return {
        "predicted_class": predicted,
        "scores": scores,
        "text": text,
        "categories": categories,
        "usage": data.get("usage", {}),
    }


@register_node("aitransform.extract_entities")
async def ait_extract_entities(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Extract named entities (people, places, organisations, dates, etc.) from text."""
    text = config.get("text") or input_data.get("text")
    if not text:
        raise ValueError("aitransform.extract_entities requires 'text'")

    entity_types = config.get("entity_types") or input_data.get("entity_types", [])
    if isinstance(entity_types, str):
        entity_types = [e.strip() for e in entity_types.split(",") if e.strip()]

    model = config.get("model") or input_data.get("model", "default")
    language = config.get("language") or input_data.get("language")
    include_context = config.get("include_context") if "include_context" in config else input_data.get("include_context", True)

    payload: dict = {
        "text": text,
        "model": model,
        "include_context": bool(include_context),
    }
    if entity_types:
        payload["entity_types"] = entity_types
    if language:
        payload["language"] = language

    async with await _client(credential_id, db) as client:
        r = await client.post("/extract-entities", json=payload)
        _raise_for_status(r)
        data = r.json()

    entities = data.get("entities", [])
    log.info("aitransform.extract_entities", entity_count=len(entities))
    return {
        "entities": entities,
        "text": text,
        "entity_count": len(entities),
        "usage": data.get("usage", {}),
    }


@register_node("aitransform.summarize_text")
async def ait_summarize_text(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Generate a concise summary of a longer piece of text."""
    text = config.get("text") or input_data.get("text")
    if not text:
        raise ValueError("aitransform.summarize_text requires 'text'")

    max_sentences = int(config.get("max_sentences") or input_data.get("max_sentences", 3))
    style = config.get("style") or input_data.get("style", "abstractive")
    model = config.get("model") or input_data.get("model", "default")
    language = config.get("language") or input_data.get("language")

    payload: dict = {
        "text": text,
        "max_sentences": max_sentences,
        "style": style,
        "model": model,
    }
    if language:
        payload["language"] = language

    async with await _client(credential_id, db) as client:
        r = await client.post("/summarize", json=payload)
        _raise_for_status(r)
        data = r.json()

    summary = data.get("summary", "")
    log.info("aitransform.summarize_text", original_length=len(text), summary_length=len(summary))
    return {
        "summary": summary,
        "original_length": len(text),
        "usage": data.get("usage", {}),
    }
