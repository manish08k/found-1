"""
Moderation nodes — content safety and policy enforcement.

Nodes:
  - moderation.openai         — OpenAI Moderation API
  - moderation.simple_prompt  — LLM-based simple prompt moderation
"""
import json
import re

import httpx
import structlog

from core.execution_engine import register_node
from core.config import settings

log = structlog.get_logger(__name__)


# ─── OpenAI Moderation ────────────────────────────────────────────────────────

@register_node("moderation.openai")
async def moderation_openai(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    OpenAI Moderation API: checks content for policy violations.
    Returns categories, scores, and whether the content is flagged.

    config:
      - input: text to moderate (supports {{ }} templates)
      - model: omni-moderation-latest | text-moderation-latest (default: omni-moderation-latest)
      - fail_on_flagged: raise an error if content is flagged (default: False)
      - threshold: minimum score to consider flagged (default: use API default)
    Requires OPENAI_API_KEY.
    """
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise ValueError(
            "moderation.openai requires OPENAI_API_KEY in environment. "
            "Obtain from https://platform.openai.com/api-keys"
        )

    def _render(t, d):
        if not isinstance(t, str):
            return t
        return re.sub(
            r"\{\{\s*([\w\.]+)\s*\}\}",
            lambda m: _deep_get(d, m.group(1).strip().split(".")) or "",
            t,
        )

    def _deep_get(obj, keys):
        for k in keys:
            obj = obj.get(k) if isinstance(obj, dict) else None
        return obj

    content = _render(
        config.get("input") or config.get("text") or "",
        input_data,
    ) or input_data.get("text") or input_data.get("input") or input_data.get("content", "")

    if not content:
        raise ValueError("moderation.openai requires 'input' or 'text' in config or input_data")

    model = config.get("model", "omni-moderation-latest")
    fail_on_flagged = config.get("fail_on_flagged", False)
    threshold = config.get("threshold")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            "https://api.openai.com/v1/moderations",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "input": content},
        )
        r.raise_for_status()
        data = r.json()

    results = data.get("results", [{}])
    result = results[0] if results else {}

    flagged = result.get("flagged", False)
    categories = result.get("categories", {})
    category_scores = result.get("category_scores", {})

    # Apply custom threshold if set
    if threshold is not None:
        flagged = any(score >= float(threshold) for score in category_scores.values())

    # Collect flagged category names
    flagged_categories = [cat for cat, val in categories.items() if val]

    log.info(
        "moderation_check",
        flagged=flagged,
        flagged_categories=flagged_categories,
        model=model,
    )

    if fail_on_flagged and flagged:
        raise ValueError(
            f"Content flagged by OpenAI moderation. "
            f"Violated categories: {', '.join(flagged_categories) or 'unknown'}"
        )

    return {
        "flagged": flagged,
        "categories": categories,
        "category_scores": category_scores,
        "flagged_categories": flagged_categories,
        "model": model,
        "input_length": len(content),
        "safe": not flagged,
    }


# ─── Simple Prompt Moderation ─────────────────────────────────────────────────

@register_node("moderation.simple_prompt")
async def moderation_simple_prompt(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    SimplePromptModeration: uses an LLM to evaluate if content violates defined rules.
    More flexible than API-based moderation — supports custom policies.

    config:
      - content: text to evaluate (supports {{ }} templates)
      - rules: list of rule strings, or a single string with newline-separated rules
      - provider: openai | anthropic (default: openai)
      - model: LLM model to use
      - fail_on_violation: raise error if content violates rules (default: False)
      - threshold: confidence threshold 0-1 (default: 0.8)
    """
    def _render(t, d):
        if not isinstance(t, str):
            return t
        return re.sub(
            r"\{\{\s*([\w\.]+)\s*\}\}",
            lambda m: str(d.get(m.group(1).strip(), "")),
            t,
        )

    content = _render(
        config.get("content") or config.get("input") or config.get("text") or "",
        input_data,
    ) or input_data.get("content") or input_data.get("text") or input_data.get("input", "")

    if not content:
        raise ValueError("moderation.simple_prompt requires 'content' in config or input_data")

    raw_rules = config.get("rules") or []
    if isinstance(raw_rules, str):
        rules = [r.strip() for r in raw_rules.strip().split("\n") if r.strip()]
    elif isinstance(raw_rules, list):
        rules = raw_rules
    else:
        rules = []

    if not rules:
        # Default safety rules
        rules = [
            "Contains hate speech, discrimination, or derogatory content",
            "Promotes violence, self-harm, or dangerous activities",
            "Contains sexually explicit content",
            "Contains personal identifiable information (PII) inappropriately",
            "Attempts to manipulate, deceive, or engage in fraud",
            "Contains spam or unsolicited commercial content",
        ]

    provider = config.get("provider", "openai")
    model = config.get("model", "")
    fail_on_violation = config.get("fail_on_violation", False)
    threshold = float(config.get("threshold", 0.8))

    rules_formatted = "\n".join(f"{i+1}. {rule}" for i, rule in enumerate(rules))

    system = (
        "You are a content safety evaluator. Your job is to check if content violates any of the given rules.\n"
        "Respond in JSON format with:\n"
        '{"violated": true/false, "violations": ["rule that was violated", ...], '
        '"confidence": 0.0-1.0, "explanation": "brief explanation"}\n'
        "Be strict but fair. Only flag clear violations."
    )

    prompt = (
        f"Rules to check:\n{rules_formatted}\n\n"
        f"Content to evaluate:\n{content}\n\n"
        "Does this content violate any of the rules? Respond in JSON:"
    )

    # Call LLM
    try:
        if provider == "anthropic":
            api_key = settings.ANTHROPIC_API_KEY
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY required")
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                    json={
                        "model": model or "claude-3-5-haiku-20241022",
                        "max_tokens": 512,
                        "system": system,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                r.raise_for_status()
                response_text = r.json()["content"][0]["text"]
        else:
            api_key = settings.OPENAI_API_KEY
            if not api_key:
                raise ValueError("OPENAI_API_KEY required")
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": model or "gpt-4o-mini",
                        "max_tokens": 512,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": prompt},
                        ],
                    },
                )
                r.raise_for_status()
                response_text = r.json()["choices"][0]["message"]["content"]

        # Parse JSON response
        json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
        else:
            parsed = {"violated": False, "violations": [], "confidence": 0.0, "explanation": response_text}

    except Exception as e:
        log.warning("moderation_simple_prompt_error", error=str(e))
        parsed = {"violated": False, "violations": [], "confidence": 0.0, "explanation": f"Evaluation error: {e}"}

    violated = parsed.get("violated", False)
    confidence = float(parsed.get("confidence", 0.0))

    # Apply confidence threshold
    if confidence < threshold:
        violated = False

    violations = parsed.get("violations", [])

    log.info(
        "simple_moderation",
        violated=violated,
        confidence=confidence,
        violations=violations,
    )

    if fail_on_violation and violated:
        raise ValueError(
            f"Content violates moderation rules. "
            f"Violations: {', '.join(violations) if violations else 'unspecified'}. "
            f"Confidence: {confidence:.2f}"
        )

    return {
        "violated": violated,
        "violations": violations,
        "confidence": confidence,
        "explanation": parsed.get("explanation", ""),
        "rules_checked": len(rules),
        "safe": not violated,
        "provider": provider,
        "model": model,
    }
