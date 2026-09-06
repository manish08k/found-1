"""
Cursor AI code editor integration.

Cursor does not have a public REST API. This integration wraps the
OpenAI-compatible endpoint that Cursor exposes for programmatic access.

Credential fields:
  - api_key: Cursor API key (or OpenAI-compatible key)
  - base_url: API base URL (default: https://api.cursor.com/v1)

Auth: Bearer token via Authorization header
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

DEFAULT_BASE_URL = "https://api.cursor.com/v1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Cursor credential missing 'api_key'")
    base_url = creds.get("base_url", DEFAULT_BASE_URL).rstrip("/")
    return httpx.AsyncClient(
        base_url=base_url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=60.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Cursor API error {r.status_code}: {detail}")
    return r.json()


@register_node("cursor.run_prompt")
async def cursor_run_prompt(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /chat/completions — execute a code generation prompt."""
    prompt = config.get("prompt") or input_data.get("prompt", "")
    model = config.get("model") or input_data.get("model", "cursor-small")
    max_tokens = config.get("max_tokens") or input_data.get("max_tokens", 2048)
    temperature = config.get("temperature", 0.7)

    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": int(max_tokens),
        "temperature": float(temperature),
    }
    async with await _client(credential_id, db) as client:
        r = await client.post("/chat/completions", json=body)
    data = _check(r)
    choice = data.get("choices", [{}])[0]
    return {
        "content": choice.get("message", {}).get("content", ""),
        "model": data.get("model", model),
        "usage": data.get("usage", {}),
    }


@register_node("cursor.get_completion")
async def cursor_get_completion(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /completions — get a code completion."""
    prompt = config.get("prompt") or input_data.get("prompt", "")
    model = config.get("model") or input_data.get("model", "cursor-small")
    max_tokens = config.get("max_tokens") or input_data.get("max_tokens", 1024)
    temperature = config.get("temperature", 0.0)

    body = {
        "model": model,
        "prompt": prompt,
        "max_tokens": int(max_tokens),
        "temperature": float(temperature),
    }
    async with await _client(credential_id, db) as client:
        r = await client.post("/completions", json=body)
    data = _check(r)
    choice = data.get("choices", [{}])[0]
    return {
        "completion": choice.get("text", ""),
        "model": data.get("model", model),
        "usage": data.get("usage", {}),
    }


@register_node("cursor.list_models")
async def cursor_list_models(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /models — list available models."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/models")
    data = _check(r)
    return {"models": data.get("data", [])}
