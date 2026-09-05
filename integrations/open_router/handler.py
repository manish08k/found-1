"""OpenRouter LLM routing integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

OPEN_ROUTER_BASE = "https://openrouter.ai/api/v1"


@register_node("open_router.chat")
async def open_router_chat(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Run a chat completion through OpenRouter.

    config/input_data:
      api_key  — OpenRouter API key
      model    — model ID (e.g. "anthropic/claude-3-haiku")
      messages — list of {"role": ..., "content": ...} dicts
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    model = merged.get("model") or "anthropic/claude-3-haiku"
    messages = merged.get("messages") or []

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": model, "messages": messages}

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{OPEN_ROUTER_BASE}/chat/completions", headers=headers, json=payload)
        r.raise_for_status()

    data = r.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    log.info("open_router.chat", model=model, response_length=len(content))
    return {"result": data, "content": content}


@register_node("open_router.list_models")
async def open_router_list_models(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List models available on OpenRouter.

    config/input_data:
      api_key — OpenRouter API key
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""

    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{OPEN_ROUTER_BASE}/models", headers=headers)
        r.raise_for_status()

    result = r.json()
    log.info("open_router.list_models", count=len(result.get("data", [])))
    return {"result": result}
