"""
Mistral AI LLM integration.

Provides chat completions, text completions, and text embeddings via the
Mistral AI API.

Credential fields:
  - api_key : Mistral AI API key

Auth: Bearer token in Authorization header.
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://api.mistral.ai/v1/"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Mistral AI credential missing 'api_key'")
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
        raise ValueError(f"Mistral AI API error {r.status_code}: {detail}")


@register_node("mistralai.chat")
async def mistralai_chat(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Send a chat completion request to Mistral AI."""
    messages = config.get("messages") or input_data.get("messages")
    if not messages:
        # Convenience: accept a single user prompt and wrap it
        prompt = config.get("prompt") or input_data.get("prompt")
        if not prompt:
            raise ValueError("mistralai.chat requires 'messages' or 'prompt'")
        messages = [{"role": "user", "content": prompt}]

    model = config.get("model") or input_data.get("model", "mistral-small-latest")
    temperature = float(config.get("temperature") or input_data.get("temperature", 0.7))
    max_tokens = config.get("max_tokens") or input_data.get("max_tokens")
    top_p = float(config.get("top_p") or input_data.get("top_p", 1.0))
    stream = False  # streaming not supported in synchronous handler

    payload: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "top_p": top_p,
        "stream": stream,
    }
    if max_tokens:
        payload["max_tokens"] = int(max_tokens)

    log.info("mistralai.chat", model=model, message_count=len(messages))
    async with await _client(credential_id, db) as client:
        r = await client.post("chat/completions", json=payload)
        _raise_for_status(r)
        data = r.json()

    choice = data.get("choices", [{}])[0]
    message = choice.get("message", {})
    return {
        "content": message.get("content", ""),
        "role": message.get("role", "assistant"),
        "model": data.get("model", model),
        "usage": data.get("usage", {}),
        "finish_reason": choice.get("finish_reason"),
        "raw": data,
    }


@register_node("mistralai.complete")
async def mistralai_complete(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Send a completion request (uses the chat endpoint with a single user message)."""
    prompt = config.get("prompt") or input_data.get("prompt")
    if not prompt:
        raise ValueError("mistralai.complete requires 'prompt'")

    model = config.get("model") or input_data.get("model", "mistral-small-latest")
    temperature = float(config.get("temperature") or input_data.get("temperature", 0.7))
    max_tokens = config.get("max_tokens") or input_data.get("max_tokens")

    payload: dict = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    if max_tokens:
        payload["max_tokens"] = int(max_tokens)

    log.info("mistralai.complete", model=model)
    async with await _client(credential_id, db) as client:
        r = await client.post("chat/completions", json=payload)
        _raise_for_status(r)
        data = r.json()

    choice = data.get("choices", [{}])[0]
    content = choice.get("message", {}).get("content", "")
    return {
        "text": content,
        "model": data.get("model", model),
        "usage": data.get("usage", {}),
        "finish_reason": choice.get("finish_reason"),
        "raw": data,
    }


@register_node("mistralai.embed")
async def mistralai_embed(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Generate text embeddings using Mistral AI."""
    input_text = config.get("input") or input_data.get("input")
    if not input_text:
        raise ValueError("mistralai.embed requires 'input' (string or list of strings)")

    model = config.get("model") or input_data.get("model", "mistral-embed")

    # Accept both single string and list
    inputs = input_text if isinstance(input_text, list) else [input_text]

    payload = {
        "model": model,
        "input": inputs,
        "encoding_format": "float",
    }

    log.info("mistralai.embed", model=model, input_count=len(inputs))
    async with await _client(credential_id, db) as client:
        r = await client.post("embeddings", json=payload)
        _raise_for_status(r)
        data = r.json()

    embeddings = [item.get("embedding", []) for item in data.get("data", [])]
    return {
        "embeddings": embeddings,
        "model": data.get("model", model),
        "usage": data.get("usage", {}),
        "raw": data,
    }
