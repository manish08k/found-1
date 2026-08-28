"""
Output parser nodes — parse LLM text output into structured formats.

Nodes:
  outputparser.csv_list           — parse comma-separated list
  outputparser.custom_list        — parse list with custom delimiter
  outputparser.structured         — parse JSON against a schema
  outputparser.structured_advanced — Pydantic-style field extraction via LLM
  outputparser.regex              — extract with regex pattern
  outputparser.datetime           — parse date/time strings
  outputparser.boolean            — extract yes/no/true/false
  outputparser.number             — extract numeric value
"""
import json
import re
from datetime import datetime
from typing import Any

import httpx
import structlog

from core.config import settings
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _get_text(input_data: dict, config: dict) -> str:
    """Get the text to parse from input or config."""
    return (
        input_data.get("text")
        or input_data.get("output")
        or input_data.get("content")
        or config.get("text", "")
    )


# ─── outputparser.csv_list ───────────────────────────────────────────────────

@register_node("outputparser.csv_list")
async def outputparser_csv_list(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Parse a comma-separated list from LLM output.
    config: strip_whitespace (bool), lowercase (bool)
    Returns: {items: list[str], count: int}
    """
    text = _get_text(input_data, config)
    strip = config.get("strip_whitespace", True)
    lowercase = config.get("lowercase", False)

    # Try to find a list-like structure first
    list_match = re.search(r"\[([^\]]+)\]", text)
    if list_match:
        text = list_match.group(1)

    items = [item.strip() if strip else item for item in text.split(",")]
    items = [item.strip('"').strip("'").strip() for item in items if item.strip()]
    if lowercase:
        items = [i.lower() for i in items]

    return {"items": items, "count": len(items), "raw": text}


# ─── outputparser.custom_list ────────────────────────────────────────────────

@register_node("outputparser.custom_list")
async def outputparser_custom_list(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Parse a list using a custom delimiter or numbering pattern.
    config: delimiter, regex_pattern, strip_whitespace, max_items
    """
    text = _get_text(input_data, config)
    delimiter = config.get("delimiter", "\n")
    pattern = config.get("regex_pattern", "")
    strip = config.get("strip_whitespace", True)
    max_items = int(config.get("max_items", 0))

    if pattern:
        items = re.findall(pattern, text)
    else:
        # Handle common numbered/bulleted lists: "1. ", "- ", "* ", "• "
        if delimiter == "\n":
            lines = text.split("\n")
            items = []
            for line in lines:
                line = line.strip() if strip else line
                # Strip common list prefixes
                line = re.sub(r"^[\d]+[\.\)]\s*", "", line)
                line = re.sub(r"^[-\*•]\s*", "", line)
                if line:
                    items.append(line)
        else:
            items = text.split(delimiter)
            if strip:
                items = [i.strip() for i in items]
            items = [i for i in items if i]

    if max_items > 0:
        items = items[:max_items]

    return {"items": items, "count": len(items), "raw": text}


# ─── outputparser.structured ─────────────────────────────────────────────────

@register_node("outputparser.structured")
async def outputparser_structured(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Parse JSON from LLM output, optionally validating against a schema.
    config: schema (dict of field→type description), strict (bool)
    """
    text = _get_text(input_data, config)
    schema = config.get("schema", {})
    strict = config.get("strict", False)

    # Try to extract JSON from the text
    parsed = None
    errors = []

    # Try direct parse
    try:
        parsed = json.loads(text)
    except Exception:
        pass

    # Try extracting from markdown code block
    if parsed is None:
        for pattern in [r"```json\s*([\s\S]+?)\s*```", r"```\s*([\s\S]+?)\s*```", r"(\{[\s\S]+\})", r"(\[[\s\S]+\])"]:
            m = re.search(pattern, text)
            if m:
                try:
                    parsed = json.loads(m.group(1))
                    break
                except Exception:
                    continue

    if parsed is None:
        if strict:
            return {"parsed": None, "valid": False, "error": "Could not parse JSON from output", "raw": text}
        return {"parsed": {}, "valid": False, "error": "Could not parse JSON", "raw": text}

    # Validate schema fields exist
    if schema and isinstance(parsed, dict):
        missing = [k for k in schema if k not in parsed]
        if missing and strict:
            return {"parsed": parsed, "valid": False, "missing_fields": missing, "raw": text}
        errors = [f"Missing field: {k}" for k in missing]

    return {"parsed": parsed, "valid": len(errors) == 0, "errors": errors, "raw": text}


# ─── outputparser.structured_advanced ────────────────────────────────────────

@register_node("outputparser.structured_advanced")
async def outputparser_structured_advanced(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Extract structured data using an LLM to fill a defined schema.
    Falls back to JSON extraction; if that fails, uses a secondary LLM call
    to extract and format the data according to the schema.
    config: schema (dict of {field: {type, description, required}}), provider, model
    """
    text = _get_text(input_data, config)
    schema = config.get("schema", {})
    provider = config.get("provider", "openai")
    model = config.get("model", "gpt-4o-mini")

    if not schema:
        return {"parsed": {}, "valid": False, "error": "No schema provided"}

    # First try direct JSON extraction
    try:
        for pattern in [r"```json\s*([\s\S]+?)\s*```", r"(\{[\s\S]+\})"]:
            m = re.search(pattern, text)
            if m:
                parsed = json.loads(m.group(1))
                if all(k in parsed for k in schema if schema[k].get("required", False)):
                    return {"parsed": parsed, "valid": True, "method": "json_extract"}
    except Exception:
        pass

    # Use LLM to extract structured data
    schema_desc = json.dumps(schema, indent=2)
    extraction_prompt = (
        f"Extract information from the text below and return it as a valid JSON object "
        f"matching this schema:\n{schema_desc}\n\n"
        f"Text to extract from:\n{text}\n\n"
        f"Return only the JSON object, no explanation:"
    )

    api_key = settings.OPENAI_API_KEY
    if not api_key:
        return {"parsed": {}, "valid": False, "error": "OPENAI_API_KEY required for structured_advanced"}

    async with httpx.AsyncClient(timeout=30) as c:
        if provider == "openai":
            r = await c.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "messages": [{"role": "user", "content": extraction_prompt}],
                      "temperature": 0.0, "max_tokens": 1024,
                      "response_format": {"type": "json_object"}},
            )
            r.raise_for_status()
            extracted = r.json()["choices"][0]["message"]["content"]
        else:
            return {"parsed": {}, "valid": False, "error": f"Only openai supported for structured_advanced, got {provider}"}

    try:
        parsed = json.loads(extracted)
        missing = [k for k, v in schema.items() if v.get("required", False) and k not in parsed]
        return {"parsed": parsed, "valid": len(missing) == 0, "missing_fields": missing, "method": "llm_extract"}
    except Exception as e:
        return {"parsed": {}, "valid": False, "error": str(e), "raw": extracted}


# ─── outputparser.regex ──────────────────────────────────────────────────────

@register_node("outputparser.regex")
async def outputparser_regex(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Extract content using a regex pattern.
    config: pattern, group (int, default 0), all_matches (bool), flags (str)
    """
    text = _get_text(input_data, config)
    pattern = config.get("pattern", r".*")
    group = int(config.get("group", 0))
    all_matches = config.get("all_matches", False)
    flags_str = config.get("flags", "")
    flags = 0
    if "i" in flags_str:
        flags |= re.IGNORECASE
    if "m" in flags_str:
        flags |= re.MULTILINE
    if "s" in flags_str:
        flags |= re.DOTALL

    if all_matches:
        matches = re.findall(pattern, text, flags)
        return {"matches": matches, "count": len(matches), "raw": text}
    else:
        m = re.search(pattern, text, flags)
        if m:
            try:
                value = m.group(group)
            except IndexError:
                value = m.group(0)
            return {"match": value, "found": True, "raw": text}
        return {"match": None, "found": False, "raw": text}


# ─── outputparser.datetime ───────────────────────────────────────────────────

@register_node("outputparser.datetime")
async def outputparser_datetime(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Parse date/time strings from LLM output.
    config: formats (list of strptime format strings), output_format
    """
    text = _get_text(input_data, config).strip()
    formats = config.get("formats", [
        "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y",
    ])
    output_format = config.get("output_format", "%Y-%m-%dT%H:%M:%S")

    for fmt in formats:
        try:
            dt = datetime.strptime(text, fmt)
            return {"datetime": dt.strftime(output_format), "parsed": True, "format_used": fmt, "raw": text}
        except ValueError:
            continue

    return {"datetime": None, "parsed": False, "error": f"Could not parse '{text}' with any known format", "raw": text}


# ─── outputparser.boolean ────────────────────────────────────────────────────

@register_node("outputparser.boolean")
async def outputparser_boolean(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Extract a boolean (yes/no, true/false) from LLM output.
    config: true_values, false_values
    """
    text = _get_text(input_data, config).strip().lower()
    true_values = config.get("true_values", ["yes", "true", "1", "correct", "affirmative", "positive"])
    false_values = config.get("false_values", ["no", "false", "0", "incorrect", "negative"])

    for tv in true_values:
        if tv.lower() in text:
            return {"value": True, "confidence": "high" if text.strip() == tv.lower() else "medium", "raw": text}
    for fv in false_values:
        if fv.lower() in text:
            return {"value": False, "confidence": "high" if text.strip() == fv.lower() else "medium", "raw": text}

    return {"value": None, "confidence": "none", "error": "Could not determine boolean", "raw": text}


# ─── outputparser.number ─────────────────────────────────────────────────────

@register_node("outputparser.number")
async def outputparser_number(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Extract a numeric value from LLM output.
    config: as_integer (bool), allow_negative (bool)
    """
    text = _get_text(input_data, config)
    as_integer = config.get("as_integer", False)
    allow_negative = config.get("allow_negative", True)

    pattern = r"-?\d+(?:\.\d+)?" if allow_negative else r"\d+(?:\.\d+)?"
    numbers = re.findall(pattern, text)

    if not numbers:
        return {"value": None, "found": False, "error": "No number found", "raw": text}

    try:
        value = int(numbers[0]) if as_integer else float(numbers[0])
        return {"value": value, "found": True, "all_found": [int(n) if as_integer else float(n) for n in numbers], "raw": text}
    except ValueError as e:
        return {"value": None, "found": False, "error": str(e), "raw": text}
