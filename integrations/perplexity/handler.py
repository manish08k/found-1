"""
Perplexity AI integration.

Auth: Bearer api_key.

Credential fields:
  - api_key (str) : Perplexity API key.

Nodes:
  - perplexity.search : Perform a web-grounded search query.
  - perplexity.chat   : Multi-turn chat completion with optional search grounding.

Base URL: https://api.perplexity.ai/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://api.perplexity.ai/"

_DEFAULT_SEARCH_MODEL = "sonar"
_DEFAULT_CHAT_MODEL = "sonar-pro"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Perplexity credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=60.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Perplexity API error {r.status_code}: {detail}")


@register_node("perplexity.search")
async def search(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Perform a web-grounded search via Perplexity.

    Config / input keys:
      - query (str, required)    : The search question.
      - model (str)              : Model to use. Default "sonar".
      - max_tokens (int)         : Max response tokens. Default 1024.
      - temperature (float)      : Sampling temperature 0–2. Default 0.2.
      - system_prompt (str)      : Optional system message prepended to the query.
      - search_recency_filter (str) : "day" | "week" | "month" | "year". Default unset.
    """
    query = config.get("query") or input_data.get("query")
    if not query:
        raise ValueError("perplexity.search requires 'query'")

    model = config.get("model") or input_data.get("model", _DEFAULT_SEARCH_MODEL)
    max_tokens = int(config.get("max_tokens") or input_data.get("max_tokens", 1024))
    temperature = float(config.get("temperature") or input_data.get("temperature", 0.2))
    system_prompt = config.get("system_prompt") or input_data.get("system_prompt", "Be precise and concise.")
    recency = config.get("search_recency_filter") or input_data.get("search_recency_filter")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query},
    ]

    payload: dict = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if recency:
        payload["search_recency_filter"] = recency

    log.info("perplexity.search", model=model, query_preview=query[:80])
    async with await _client(credential_id, db) as client:
        r = await client.post("chat/completions", json=payload)
        _raise_for_status(r)
        data = r.json()

    choices = data.get("choices", [])
    answer = choices[0].get("message", {}).get("content", "") if choices else ""
    citations = data.get("citations", [])

    return {
        "query": query,
        "answer": answer,
        "citations": citations,
        "model": data.get("model"),
        "usage": data.get("usage", {}),
        "raw": data,
    }


@register_node("perplexity.chat")
async def chat(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Multi-turn chat completion via Perplexity.

    Config / input keys:
      - messages (list, required)  : List of {"role": ..., "content": ...} message dicts.
                                     Alternatively pass 'prompt' for a single user message.
      - model (str)                : Model to use. Default "sonar-pro".
      - max_tokens (int)           : Max tokens. Default 2048.
      - temperature (float)        : Temperature 0–2. Default 0.7.
      - system_prompt (str)        : Optional system message (prepended if no system msg present).
    """
    messages = config.get("messages") or input_data.get("messages")
    prompt = config.get("prompt") or input_data.get("prompt")

    if not messages and not prompt:
        raise ValueError("perplexity.chat requires 'messages' or 'prompt'")

    if not messages:
        messages = [{"role": "user", "content": prompt}]

    # Inject system prompt if not already present
    system_prompt = config.get("system_prompt") or input_data.get("system_prompt")
    if system_prompt and (not messages or messages[0].get("role") != "system"):
        messages = [{"role": "system", "content": system_prompt}] + list(messages)

    model = config.get("model") or input_data.get("model", _DEFAULT_CHAT_MODEL)
    max_tokens = int(config.get("max_tokens") or input_data.get("max_tokens", 2048))
    temperature = float(config.get("temperature") or input_data.get("temperature", 0.7))

    payload: dict = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    log.info("perplexity.chat", model=model, message_count=len(messages))
    async with await _client(credential_id, db) as client:
        r = await client.post("chat/completions", json=payload)
        _raise_for_status(r)
        data = r.json()

    choices = data.get("choices", [])
    reply = choices[0].get("message", {}).get("content", "") if choices else ""

    return {
        "reply": reply,
        "model": data.get("model"),
        "usage": data.get("usage", {}),
        "finish_reason": choices[0].get("finish_reason") if choices else None,
        "citations": data.get("citations", []),
        "raw": data,
    }
