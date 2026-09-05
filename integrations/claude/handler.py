"""Anthropic Claude API integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

CLAUDE_BASE = "https://api.anthropic.com/v1"
ANTHROPIC_VERSION = "2023-06-01"


def _build_headers(api_key: str) -> dict:
    return {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "Content-Type": "application/json",
    }


def _build_payload(merged: dict) -> dict:
    model = merged.get("model") or "claude-opus-4-5"
    messages = merged.get("messages") or []
    max_tokens = int(merged.get("max_tokens", 1024))
    payload: dict = {"model": model, "max_tokens": max_tokens, "messages": messages}
    system = merged.get("system")
    if system:
        payload["system"] = system
    return payload


@register_node("claude.message")
async def claude_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a message to Claude and receive a response.

    config/input_data:
      api_key    — Anthropic API key
      model      — model ID (default "claude-opus-4-5")
      messages   — list of {"role": ..., "content": ...} dicts
      max_tokens — maximum tokens in response (default 1024)
      system     — optional system prompt string
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    headers = _build_headers(api_key)
    payload = _build_payload(merged)

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{CLAUDE_BASE}/messages", headers=headers, json=payload)
        r.raise_for_status()

    data = r.json()
    content = ""
    if data.get("content"):
        content = data["content"][0].get("text", "")
    log.info("claude.message", model=payload["model"], stop_reason=data.get("stop_reason"))
    return {"result": data, "content": content}


@register_node("claude.count_tokens")
async def claude_count_tokens(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Count tokens for a Claude messages payload.

    config/input_data:
      api_key    — Anthropic API key
      model      — model ID (default "claude-opus-4-5")
      messages   — list of {"role": ..., "content": ...} dicts
      max_tokens — max_tokens field (default 1024)
      system     — optional system prompt string
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    headers = _build_headers(api_key)
    payload = _build_payload(merged)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{CLAUDE_BASE}/messages/count_tokens", headers=headers, json=payload)
        r.raise_for_status()

    result = r.json()
    log.info("claude.count_tokens", input_tokens=result.get("input_tokens"))
    return {"result": result}
