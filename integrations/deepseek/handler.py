"""DeepSeek LLM integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

DEEPSEEK_BASE = "https://api.deepseek.com/v1"


@register_node("deepseek.chat")
async def deepseek_chat(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Run a chat completion using DeepSeek.

    config/input_data:
      api_key     — DeepSeek API key
      model       — model ID (default "deepseek-chat")
      messages    — list of {"role": ..., "content": ...} dicts
      temperature — sampling temperature (default 0.7)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    model = merged.get("model") or "deepseek-chat"
    messages = merged.get("messages") or []
    temperature = float(merged.get("temperature", 0.7))

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": model, "messages": messages, "temperature": temperature}

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{DEEPSEEK_BASE}/chat/completions", headers=headers, json=payload)
        r.raise_for_status()

    data = r.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    log.info("deepseek.chat", model=model, response_length=len(content))
    return {"result": data, "content": content}


@register_node("deepseek.list_models")
async def deepseek_list_models(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List available DeepSeek models.

    config/input_data:
      api_key — DeepSeek API key
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""

    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{DEEPSEEK_BASE}/models", headers=headers)
        r.raise_for_status()

    result = r.json()
    log.info("deepseek.list_models", count=len(result.get("data", [])))
    return {"result": result}
