"""
Prompt template nodes — build structured prompts for LLM calls.

Nodes:
  prompt.template               — simple {{variable}} substitution
  prompt.chat_template          — system + human message template
  prompt.few_shot               — examples + template
  prompt.langfuse               — fetch prompt from Langfuse prompt registry
  prompt.format_messages        — convert list of role/content pairs to prompt
  prompt.conditional            — choose a template based on a condition
"""
import json
import re
from typing import Any

import httpx
import structlog

from core.config import settings
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _render(template: str, variables: dict) -> str:
    """Render {{variable}} placeholders."""
    if not isinstance(template, str):
        return str(template) if template is not None else ""

    def repl(m):
        path = m.group(1).strip().split(".")
        val: Any = variables
        for p in path:
            val = val.get(p) if isinstance(val, dict) else None
        if val is None:
            return m.group(0)  # keep original if not found
        return val if isinstance(val, str) else json.dumps(val)

    return re.sub(r"\{\{\s*([\w\.]+)\s*\}\}", repl, template)


# ─── prompt.template ─────────────────────────────────────────────────────────

@register_node("prompt.template")
async def prompt_template(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Simple string prompt with {{variable}} substitution.
    config: template (str), variables (dict of extra vars to merge)
    input_data: any key used in {{...}} placeholders
    Returns: {prompt: str, variables_used: list}
    """
    template = config.get("template", "{{input}}")
    extra_vars = config.get("variables", {})
    merged = {**input_data, **extra_vars}

    prompt = _render(template, merged)

    # Find which variables were actually used
    used = re.findall(r"\{\{\s*([\w\.]+)\s*\}\}", template)
    return {"prompt": prompt, "variables_used": list(set(used)), "template": template}


# ─── prompt.chat_template ────────────────────────────────────────────────────

@register_node("prompt.chat_template")
async def prompt_chat_template(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Chat prompt with separate system/human/AI template sections.
    config:
      system_template: str
      human_template: str
      ai_template: str (optional, for few-shot examples)
      partial_variables: dict
      messages: list of {role, template} for multi-turn templates
    Returns: {messages: list[{role, content}], prompt: str}
    """
    extra_vars = config.get("partial_variables", {})
    merged = {**input_data, **extra_vars}

    messages = []

    # Handle explicit messages list
    if "messages" in config:
        for msg in config["messages"]:
            role = msg.get("role", "user")
            tmpl = msg.get("template", msg.get("content", ""))
            content = _render(tmpl, merged)
            if content.strip():
                messages.append({"role": role, "content": content})
    else:
        system_tmpl = config.get("system_template", "You are a helpful assistant.")
        human_tmpl = config.get("human_template", "{{input}}")
        ai_tmpl = config.get("ai_template", "")

        system_content = _render(system_tmpl, merged)
        human_content = _render(human_tmpl, merged)

        if system_content.strip():
            messages.append({"role": "system", "content": system_content})
        if ai_tmpl.strip():
            messages.append({"role": "assistant", "content": _render(ai_tmpl, merged)})
        if human_content.strip():
            messages.append({"role": "user", "content": human_content})

    # Also produce a flattened text prompt for non-chat models
    prompt = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages)
    return {"messages": messages, "prompt": prompt, "message_count": len(messages)}


# ─── prompt.few_shot ─────────────────────────────────────────────────────────

@register_node("prompt.few_shot")
async def prompt_few_shot(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Few-shot prompt template: prefix + examples + suffix.
    config:
      prefix: str — context/instruction before examples
      examples: list of {input, output} dicts
      example_separator: str (default "\\n\\n")
      input_template: str (template for formatting each example's input)
      output_template: str (template for formatting each example's output)
      suffix: str — the template for the actual query
      input_variables: list of variable names used in suffix
    """
    prefix = _render(config.get("prefix", ""), input_data)
    suffix_tmpl = config.get("suffix", "Input: {{input}}\nOutput:")
    suffix = _render(suffix_tmpl, input_data)
    separator = config.get("example_separator", "\n\n")
    examples = config.get("examples", [])
    input_tmpl = config.get("input_template", "Input: {input}")
    output_tmpl = config.get("output_template", "Output: {output}")
    max_examples = int(config.get("max_examples", 0))

    if max_examples > 0:
        examples = examples[:max_examples]

    example_strings = []
    for ex in examples:
        ex_in = input_tmpl.replace("{input}", str(ex.get("input", "")))
        ex_out = output_tmpl.replace("{output}", str(ex.get("output", "")))
        example_strings.append(f"{ex_in}\n{ex_out}")

    parts = []
    if prefix.strip():
        parts.append(prefix)
    if example_strings:
        parts.append(separator.join(example_strings))
    parts.append(suffix)

    prompt = separator.join(parts)
    return {"prompt": prompt, "example_count": len(examples), "prefix": prefix, "suffix": suffix}


# ─── prompt.langfuse ─────────────────────────────────────────────────────────

@register_node("prompt.langfuse")
async def prompt_langfuse(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Fetch a compiled prompt from the Langfuse prompt registry.
    config: prompt_name, version (optional), label (optional), variables (dict)
    Requires LANGFUSE_SECRET_KEY and LANGFUSE_PUBLIC_KEY.
    """
    prompt_name = config.get("prompt_name") or config.get("name", "")
    version = config.get("version")
    label = config.get("label", "production")
    extra_vars = config.get("variables", {})
    merged = {**input_data, **extra_vars}

    secret_key = getattr(settings, "LANGFUSE_SECRET_KEY", "") or config.get("secret_key", "")
    public_key = getattr(settings, "LANGFUSE_PUBLIC_KEY", "") or config.get("public_key", "")
    host = getattr(settings, "LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not secret_key or not prompt_name:
        return {"prompt": config.get("fallback_template", "{{input}}"), "source": "fallback"}

    import base64
    token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    headers = {"Authorization": f"Basic {token}"}

    params: dict = {"name": prompt_name}
    if version is not None:
        params["version"] = str(version)
    elif label:
        params["label"] = label

    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{host}/api/public/v2/prompts/{prompt_name}", headers=headers, params=params)
        if r.status_code == 404:
            return {"prompt": config.get("fallback_template", "{{input}}"), "source": "fallback", "error": "Prompt not found"}
        r.raise_for_status()
        data = r.json()

    prompt_content = data.get("prompt", "")

    # Langfuse uses {{variable}} format
    rendered = _render(prompt_content, merged)

    messages = data.get("config", {}).get("messages", [])
    if messages:
        rendered_messages = [{"role": m.get("role", "user"), "content": _render(m.get("content", ""), merged)}
                             for m in messages]
        return {"prompt": rendered, "messages": rendered_messages, "source": "langfuse", "version": data.get("version")}

    return {"prompt": rendered, "source": "langfuse", "version": data.get("version"), "name": prompt_name}


# ─── prompt.format_messages ──────────────────────────────────────────────────

@register_node("prompt.format_messages")
async def prompt_format_messages(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Convert a list of message dicts into a formatted prompt string or chat messages list.
    config: format (chat|text|markdown), include_system (bool)
    input: messages (list of {role, content})
    """
    messages = input_data.get("messages") or config.get("messages", [])
    fmt = config.get("format", "chat")
    include_system = config.get("include_system", True)

    if not include_system:
        messages = [m for m in messages if m.get("role") != "system"]

    if fmt == "chat":
        return {"messages": messages, "message_count": len(messages)}

    if fmt == "text":
        lines = [f"{m.get('role', 'user').capitalize()}: {m.get('content', '')}" for m in messages]
        return {"prompt": "\n".join(lines), "messages": messages}

    if fmt == "markdown":
        parts = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            prefix = {"system": "**System**", "user": "**Human**", "assistant": "**Assistant**"}.get(role, f"**{role}**")
            parts.append(f"{prefix}: {content}")
        return {"prompt": "\n\n".join(parts), "messages": messages}

    return {"messages": messages, "prompt": str(messages)}


# ─── prompt.conditional ──────────────────────────────────────────────────────

@register_node("prompt.conditional")
async def prompt_conditional(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Select and render one of N templates based on a condition.
    config:
      conditions: list of {condition_key, condition_value, template}
      default_template: str
    """
    conditions = config.get("conditions", [])
    default_template = config.get("default_template", "{{input}}")

    selected_template = default_template
    matched_condition = None

    for cond in conditions:
        key = cond.get("condition_key", "")
        expected = cond.get("condition_value")
        actual = input_data.get(key)

        # Support string comparison, equality, and contains
        if actual is None:
            continue
        operator = cond.get("operator", "equals")
        if operator == "equals" and str(actual) == str(expected):
            selected_template = cond.get("template", default_template)
            matched_condition = cond
            break
        elif operator == "contains" and str(expected).lower() in str(actual).lower():
            selected_template = cond.get("template", default_template)
            matched_condition = cond
            break
        elif operator == "truthy" and bool(actual):
            selected_template = cond.get("template", default_template)
            matched_condition = cond
            break

    prompt = _render(selected_template, input_data)
    return {"prompt": prompt, "matched_condition": matched_condition, "template_used": selected_template}
