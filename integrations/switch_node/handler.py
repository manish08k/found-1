"""Switch integration — multi-branch conditional routing."""
import operator
import structlog
import httpx  # noqa: F401 — standard import kept for consistency

from core.execution_engine import register_node
from oauth.flow import get_credential_data  # noqa: F401 — standard import

log = structlog.get_logger(__name__)

# Supported comparison operators
_OPERATORS = {
    "equals": operator.eq,
    "not_equals": operator.ne,
    "greater_than": operator.gt,
    "less_than": operator.lt,
    "greater_than_or_equal": operator.ge,
    "less_than_or_equal": operator.le,
    "contains": lambda a, b: str(b) in str(a),
    "not_contains": lambda a, b: str(b) not in str(a),
    "starts_with": lambda a, b: str(a).startswith(str(b)),
    "ends_with": lambda a, b: str(a).endswith(str(b)),
    "is_empty": lambda a, _: a is None or a == "" or a == [] or a == {},
    "is_not_empty": lambda a, _: a is not None and a != "" and a != [] and a != {},
    "regex": lambda a, b: __import__("re").search(str(b), str(a)) is not None,
}


def _resolve_field(data: dict, field_path: str):
    """Resolve a dot-notation field path from the input data dict."""
    parts = field_path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _evaluate_rule(rule: dict, input_data: dict) -> bool:
    """Return True if input_data satisfies the given rule dict."""
    field = rule.get("condition_field", "")
    op_name = rule.get("operator", "equals")
    expected = rule.get("value")

    actual = _resolve_field(input_data, field)
    op_fn = _OPERATORS.get(op_name)
    if op_fn is None:
        log.warning("switch_node.unknown_operator", operator=op_name)
        return False

    try:
        # Attempt type coercion so "42" == 42 is handled gracefully
        if isinstance(expected, (int, float)) and isinstance(actual, str):
            try:
                actual = type(expected)(actual)
            except (ValueError, TypeError):
                pass
        return bool(op_fn(actual, expected))
    except Exception as exc:
        log.warning("switch_node.rule_eval_error", error=str(exc))
        return False


@register_node("switch_node.route")
async def switch_node_route(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Evaluates routing rules and returns the first matching branch.

    config:
      mode  (str): "expression" or "rules" (currently only "rules" is evaluated).
      rules (list): list of dicts with keys:
                    condition_field, operator, value, output (int index).
    """
    mode = config.get("mode", "rules")
    rules = config.get("rules") or input_data.get("rules", [])

    log.info("switch_node.route", mode=mode, rule_count=len(rules))

    if mode == "expression":
        # Expression mode: evaluate the raw Python expression provided
        expression = config.get("expression") or input_data.get("expression", "False")
        try:
            matched = bool(eval(expression, {"__builtins__": {}}, {"data": input_data}))  # noqa: S307
        except Exception as exc:
            log.warning("switch_node.expression_error", error=str(exc))
            matched = False

        return {
            "matched_rule": None,
            "output_index": 0 if matched else 1,
            "input_data": input_data,
            "mode": mode,
        }

    # Rules mode — evaluate each rule in order, return first match
    for idx, rule in enumerate(rules):
        if _evaluate_rule(rule, input_data):
            output_index = rule.get("output", idx)
            log.info("switch_node.rule_matched", rule_index=idx, output_index=output_index)
            return {
                "matched_rule": rule,
                "matched_rule_index": idx,
                "output_index": output_index,
                "input_data": input_data,
                "mode": mode,
            }

    # No rule matched — fall through to the default (last) output
    log.info("switch_node.no_match", rule_count=len(rules))
    return {
        "matched_rule": None,
        "matched_rule_index": None,
        "output_index": len(rules),  # one past the last named output = default branch
        "input_data": input_data,
        "mode": mode,
    }
