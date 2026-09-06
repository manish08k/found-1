"""Perplexity AI search-powered chat (Activepieces variant) — handler for perplexity_ai integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.perplexity.ai"


@register_node("perplexity_ai.chat")
async def perplexity_ai_chat(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a chat completion request.

    config/input_data:
      api_key — API key or token (required)
      model — (required)
      messages — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    model = merged.get("model") or ""
    messages = merged.get("messages") or ""
    if not model or not messages:
        raise ValueError("model, messages required for perplexity_ai.chat")
    payload = {"model": model, "messages": messages}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/chat/completions", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("perplexity_ai.chat")
    return {"data": data}
