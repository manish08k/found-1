"""
AI / LLM nodes.

  - ai.chat       — send a prompt to an LLM (Anthropic Claude or OpenAI),
                    with optional templating from the upstream node's output
                    and an optional system prompt. Returns the model's text.
  - ai.extract    — ask the LLM to extract structured data matching a JSON
                    schema description, returned as parsed JSON. Useful for
                    classification/routing before a core.condition node.

Both nodes use whichever provider is configured via ANTHROPIC_API_KEY /
OPENAI_API_KEY in the environment — no per-user OAuth credential needed,
since these are server-side API keys shared across the workflow (operator
sets them up once, like SMTP).
"""
import json
import re

import httpx
import structlog

from core.execution_engine import register_node
from core.config import settings

log = structlog.get_logger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


def _render_template(template: str, input_data: dict) -> str:
    """Replace {{field}} or {{a.b.c}} placeholders with values from input_data."""
    if not isinstance(template, str):
        return template

    def repl(match):
        path = match.group(1).strip().split(".")
        val = input_data
        for part in path:
            if isinstance(val, dict):
                val = val.get(part)
            else:
                return ""
        if val is None:
            return ""
        return val if isinstance(val, str) else json.dumps(val)

    return re.sub(r"\{\{\s*([\w\.]+)\s*\}\}", repl, template)


def _pick_provider(config: dict) -> str:
    provider = config.get("provider", "auto")
    if provider == "auto":
        if settings.ANTHROPIC_API_KEY:
            return "anthropic"
        if settings.OPENAI_API_KEY:
            return "openai"
        raise ValueError(
            "No AI provider configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY "
            "in the environment, or choose a provider explicitly."
        )
    return provider


async def _call_anthropic(model: str, system: str, prompt: str, max_tokens: int, temperature: float) -> str:
    if not settings.ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is not set in the environment.")

    payload = {
        "model": model or DEFAULT_ANTHROPIC_MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        payload["system"] = system

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            ANTHROPIC_API_URL,
            json=payload,
            headers={
                "x-api-key": settings.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        r.raise_for_status()
        data = r.json()

    parts = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
    return "\n".join(parts)


async def _call_openai(model: str, system: str, prompt: str, max_tokens: int, temperature: float) -> str:
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set in the environment.")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model or DEFAULT_OPENAI_MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            OPENAI_API_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "content-type": "application/json",
            },
        )
        r.raise_for_status()
        data = r.json()

    return data["choices"][0]["message"]["content"]


async def _call_llm(provider: str, model: str, system: str, prompt: str, max_tokens: int, temperature: float) -> str:
    if provider == "anthropic":
        return await _call_anthropic(model, system, prompt, max_tokens, temperature)
    elif provider == "openai":
        return await _call_openai(model, system, prompt, max_tokens, temperature)
    raise ValueError(f"Unknown AI provider: {provider}")


async def _record_cost_if_available(config: dict, provider: str, model: str, prompt: str, text: str, latency_ms: int, db):
    """Best-effort cost recording for LLM calls."""
    try:
        execution_id = config.get("_execution_id")
        node_id = config.get("_node_id")
        if not execution_id:
            return
        # Rough token estimation: ~4 chars per token
        input_tokens = len(prompt) // 4
        output_tokens = len(text) // 4
        actual_model = model or (DEFAULT_ANTHROPIC_MODEL if provider == "anthropic" else DEFAULT_OPENAI_MODEL)

        from core.cost_tracker import record_cost
        await record_cost(
            execution_id=execution_id,
            node_id=node_id,
            node_type=config.get("_node_type", "ai.chat"),
            model=actual_model,
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            db=db,
        )
    except Exception:
        pass  # Cost recording is best-effort


@register_node("ai.chat")
async def ai_chat(config: dict, input_data: dict, credential_id: str, db) -> dict:
    provider = _pick_provider(config)
    model = config.get("model", "")
    system_prompt = _render_template(config.get("system_prompt", ""), input_data)
    prompt = _render_template(config.get("prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 1024))
    temperature = float(config.get("temperature", 0.7))

    if not prompt:
        raise ValueError("ai.chat requires a non-empty 'prompt'.")

    import time as _time
    _start = _time.monotonic()
    text = await _call_llm(provider, model, system_prompt, prompt, max_tokens, temperature)
    _latency = int((_time.monotonic() - _start) * 1000)

    actual_model = model or (DEFAULT_ANTHROPIC_MODEL if provider == "anthropic" else DEFAULT_OPENAI_MODEL)
    await _record_cost_if_available(config, provider, actual_model, prompt, text, _latency, db)

    return {"text": text, "provider": provider, "model": actual_model}


@register_node("ai.extract")
async def ai_extract(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Ask the LLM to extract/classify data from the input and return strict JSON.

    config:
      - schema_description: plain-English description of the fields wanted,
        e.g. "category: one of 'sales','support','spam'; urgency: 1-5; summary: string"
      - text: the text to analyze (templated from input_data); defaults to
        the whole input_data as JSON if not provided.
    """
    provider = _pick_provider(config)
    model = config.get("model", "")
    max_tokens = int(config.get("max_tokens", 1024))

    schema_description = config.get("schema_description", "")
    if not schema_description:
        raise ValueError("ai.extract requires 'schema_description'.")

    text = config.get("text")
    text = _render_template(text, input_data) if text else json.dumps(input_data)

    system_prompt = (
        "You extract structured data and respond with ONLY a single valid JSON "
        "object — no markdown fences, no commentary, no explanation."
    )
    prompt = (
        f"From the following input, extract fields matching this description:\n"
        f"{schema_description}\n\n"
        f"Input:\n{text}\n\n"
        f"Respond with only the JSON object."
    )

    raw = await _call_llm(provider, model, system_prompt, prompt, max_tokens, 0)

    # Strip accidental markdown fences if the model adds them anyway.
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()

    try:
        parsed = json.loads(cleaned)
    except Exception as e:
        return {"parsed": None, "raw": raw, "error": f"Could not parse JSON: {e}"}

    result = {"raw": raw}
    if isinstance(parsed, dict):
        result.update(parsed)
    else:
        result["parsed"] = parsed
    return result


@register_node("ai.chat_with_memory")
async def ai_chat_with_memory(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Like ai.chat, but persists conversation history (storage.models.MemoryMessage)
    keyed by conversation_id, and includes prior turns as context on every
    call — the missing "Memory" primitive this project's AI nodes didn't
    have. One workflow can hold many independent conversations (e.g. one
    per end user) by using a different conversation_id per caller.
    """
    from sqlalchemy import select
    from storage.models import MemoryMessage

    workflow_id = config.get("_workflow_id")  # injected by the execution engine, see core/execution_engine.py
    conversation_id = config.get("conversation_id") or input_data.get("conversation_id")
    if not conversation_id:
        raise ValueError("ai.chat_with_memory requires 'conversation_id'")
    if not workflow_id:
        raise ValueError("ai.chat_with_memory could not resolve the current workflow — internal wiring issue")

    provider = _pick_provider(config)
    model = config.get("model", "")
    system_prompt = _render_template(config.get("system_prompt", ""), input_data)
    prompt = _render_template(config.get("prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 1024))
    temperature = float(config.get("temperature", 0.7))
    max_history_messages = int(config.get("max_history_messages", 20))
    if not prompt:
        raise ValueError("ai.chat_with_memory requires a non-empty 'prompt'.")

    history_result = await db.execute(
        select(MemoryMessage)
        .where(MemoryMessage.workflow_id == workflow_id, MemoryMessage.conversation_id == conversation_id)
        .order_by(MemoryMessage.created_at.asc())
        .limit(max_history_messages)
    )
    history = history_result.scalars().all()

    # Fold prior turns into the prompt — kept simple (a rendered transcript
    # in the user-turn prompt) rather than each provider's native
    # multi-turn message array, so this works identically regardless of
    # which provider _call_llm ends up using.
    transcript = "\n".join(f"{m.role}: {m.content}" for m in history)
    full_prompt = f"{transcript}\nuser: {prompt}" if transcript else prompt

    text = await _call_llm(provider, model, system_prompt, full_prompt, max_tokens, temperature)

    db.add(MemoryMessage(workflow_id=workflow_id, conversation_id=conversation_id, role="user", content=prompt))
    db.add(MemoryMessage(workflow_id=workflow_id, conversation_id=conversation_id, role="assistant", content=text))

    return {
        "text": text, "provider": provider, "conversation_id": conversation_id,
        "history_length": len(history) + 2,
    }


@register_node("ai.clear_memory")
async def ai_clear_memory(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Wipes a conversation's stored history — e.g. on a user saying 'start over' or a session ending."""
    from sqlalchemy import delete
    from storage.models import MemoryMessage

    workflow_id = config.get("_workflow_id")
    conversation_id = config.get("conversation_id") or input_data.get("conversation_id")
    if not conversation_id:
        raise ValueError("ai.clear_memory requires 'conversation_id'")

    result = await db.execute(
        delete(MemoryMessage).where(MemoryMessage.workflow_id == workflow_id, MemoryMessage.conversation_id == conversation_id)
    )
    return {"cleared": True, "conversation_id": conversation_id, "messages_deleted": result.rowcount}


@register_node("ai.moderate")
async def ai_moderate(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Content moderation — the "Safety & Control" primitive for input
    moderation / output post-processing. Uses OpenAI's dedicated
    (free) moderation endpoint when an OpenAI key is configured — it's
    a purpose-built classifier, more reliable than asking a general chat
    model to self-judge. Falls back to an LLM-as-judge prompt against
    whichever provider IS configured, for deployments running
    Anthropic-only.
    """
    text = config.get("text") or input_data.get("text")
    text = _render_template(text, input_data) if isinstance(text, str) else text
    if not text:
        raise ValueError("ai.moderate requires 'text'")

    if settings.OPENAI_API_KEY:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://api.openai.com/v1/moderations",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                json={"input": text},
            )
            r.raise_for_status()
            result = r.json()["results"][0]
        flagged_categories = [k for k, v in result["categories"].items() if v]
        return {"flagged": result["flagged"], "categories": flagged_categories, "scores": result["category_scores"]}

    # Fallback: LLM-as-judge, strict-JSON output, reusing ai.extract's pattern.
    provider = _pick_provider(config)
    system_prompt = (
        "You are a content moderation classifier. Respond with ONLY a JSON object: "
        '{"flagged": true|false, "categories": ["..."], "reason": "..."}. '
        "Flag content that is hateful, violent, sexual (involving minors especially), "
        "or promotes self-harm. Be conservative — only flag clear violations."
    )
    raw = await _call_llm(provider, config.get("model", ""), system_prompt, text, 300, 0)
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        parsed = json.loads(cleaned)
    except Exception:
        return {"flagged": False, "categories": [], "error": "moderation classifier returned unparseable output — treat as unmoderated, not as clean"}
    return {"flagged": parsed.get("flagged", False), "categories": parsed.get("categories", []), "reason": parsed.get("reason")}
    return result