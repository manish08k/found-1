"""Groq LLM inference integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

GROQ_BASE = "https://api.groq.com/openai/v1"


@register_node("groq.chat")
async def groq_chat(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Run a chat completion using Groq.

    config/input_data:
      api_key  — Groq API key
      model    — model ID (e.g. "llama3-8b-8192")
      messages — list of {"role": ..., "content": ...} dicts
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    model = merged.get("model") or "llama3-8b-8192"
    messages = merged.get("messages") or []

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": model, "messages": messages}

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{GROQ_BASE}/chat/completions", headers=headers, json=payload)
        r.raise_for_status()

    data = r.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    log.info("groq.chat", model=model, response_length=len(content))
    return {"result": data, "content": content}


@register_node("groq.list_models")
async def groq_list_models(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List available Groq models.

    config/input_data:
      api_key — Groq API key
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""

    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{GROQ_BASE}/models", headers=headers)
        r.raise_for_status()

    result = r.json()
    log.info("groq.list_models", count=len(result.get("data", [])))
    return {"result": result}
