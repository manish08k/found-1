"""Jina AI (Activepieces variant) — handler for jina_ai integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.jina.ai/v1"


@register_node("jina_ai.embed")
async def jina_ai_embed(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Generate embeddings.

    config/input_data:
      api_key — API key or token (required)
      model — (required)
      input — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    model = merged.get("model") or ""
    input = merged.get("input") or ""
    if not model or not input:
        raise ValueError("model, input required for jina_ai.embed")
    payload = {"model": model, "input": input}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/embeddings", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("jina_ai.embed")
    return {"data": data}

@register_node("jina_ai.rerank")
async def jina_ai_rerank(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Rerank results.

    config/input_data:
      api_key — API key or token (required)
      model — (required)
      query — (required)
      documents — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    model = merged.get("model") or ""
    query = merged.get("query") or ""
    documents = merged.get("documents") or ""
    if not model or not query or not documents:
        raise ValueError("model, query, documents required for jina_ai.rerank")
    payload = {"model": model, "query": query, "documents": documents}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/rerank", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("jina_ai.rerank")
    return {"data": data}

@register_node("jina_ai.classify")
async def jina_ai_classify(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Classify text.

    config/input_data:
      api_key — API key or token (required)
      model — (required)
      input — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    model = merged.get("model") or ""
    input = merged.get("input") or ""
    if not model or not input:
        raise ValueError("model, input required for jina_ai.classify")
    payload = {"model": model, "input": input}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/classify", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("jina_ai.classify")
    return {"data": data}
