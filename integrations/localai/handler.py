"""LocalAI self-hosted LLM integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


@register_node("localai.chat")
async def localai_chat(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Run a chat completion using a LocalAI self-hosted model.

    config/input_data:
      base_url — LocalAI base URL (e.g. "http://localhost:8080/v1")
      api_key  — optional Bearer token
      model    — model name to use
      messages — list of {"role": ..., "content": ...} dicts
    """
    merged = {**config, **input_data}
    base_url = (merged.get("base_url") or "http://localhost:8080/v1").rstrip("/")
    api_key = merged.get("api_key") or ""
    model = merged.get("model") or "gpt-4"
    messages = merged.get("messages") or []

    headers: dict = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {"model": model, "messages": messages}

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
        r.raise_for_status()

    data = r.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    log.info("localai.chat", model=model, base_url=base_url, response_length=len(content))
    return {"result": data, "content": content}


@register_node("localai.list_models")
async def localai_list_models(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List models available on a LocalAI instance.

    config/input_data:
      base_url — LocalAI base URL (e.g. "http://localhost:8080/v1")
      api_key  — optional Bearer token
    """
    merged = {**config, **input_data}
    base_url = (merged.get("base_url") or "http://localhost:8080/v1").rstrip("/")
    api_key = merged.get("api_key") or ""

    headers: dict = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base_url}/models", headers=headers)
        r.raise_for_status()

    result = r.json()
    log.info("localai.list_models", base_url=base_url, count=len(result.get("data", [])))
    return {"result": result}
