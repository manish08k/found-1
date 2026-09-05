"""
If — conditional branching node.

Evaluates a condition against input data and routes execution to a
"true" or "false" branch.

No credentials required.

Nodes:
  - if_node.branch : evaluate a condition and return branch decision

Supported operators:
  equal, not_equal, greater, less, contains, not_contains,
  starts_with, ends_with, regex_match
"""
import re
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

_VALID_OPERATORS = frozenset({
    "equal", "not_equal", "greater", "less",
    "contains", "not_contains", "starts_with", "ends_with", "regex_match",
})


def _coerce(value: str) -> object:
    """Try to coerce a string to int/float for numeric comparisons."""
    try:
        return int(value)
    except (ValueError, TypeError):
        pass
    try:
        return float(value)
    except (ValueError, TypeError):
        pass
    return value


def _evaluate(left, operator: str, right) -> bool:
    """Evaluate the condition and return a bool result."""
    op = operator.lower().strip()
    if op not in _VALID_OPERATORS:
        raise ValueError(
            f"if_node: unsupported operator '{operator}'. "
            f"Valid operators: {sorted(_VALID_OPERATORS)}"
        )

    left_str = str(left) if left is not None else ""
    right_str = str(right) if right is not None else ""

    if op == "equal":
        # Try numeric comparison first
        left_c = _coerce(left_str)
        right_c = _coerce(right_str)
        if type(left_c) == type(right_c) and not isinstance(left_c, str):
            return left_c == right_c
        return left_str == right_str

    if op == "not_equal":
        left_c = _coerce(left_str)
        right_c = _coerce(right_str)
        if type(left_c) == type(right_c) and not isinstance(left_c, str):
            return left_c != right_c
        return left_str != right_str

    if op == "greater":
        left_c = _coerce(left_str)
        right_c = _coerce(right_str)
        return float(left_c) > float(right_c)  # raises ValueError if not numeric

    if op == "less":
        left_c = _coerce(left_str)
        right_c = _coerce(right_str)
        return float(left_c) < float(right_c)

    if op == "contains":
        return right_str in left_str

    if op == "not_contains":
        return right_str not in left_str

    if op == "starts_with":
        return left_str.startswith(right_str)

    if op == "ends_with":
        return left_str.endswith(right_str)

    if op == "regex_match":
        return bool(re.search(right_str, left_str))

    return False  # unreachable


def _resolve_value(value, input_data: dict):
    """
    If `value` is a string beginning with '{{' it is treated as a template
    referencing a key in input_data, e.g. '{{email}}' → input_data['email'].
    Otherwise the raw value is returned.
    """
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if stripped.startswith("{{") and stripped.endswith("}}"):
        key = stripped[2:-2].strip()
        return input_data.get(key, value)
    return value


@register_node("if_node.branch")
async def if_branch(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Evaluate a condition and return a branch decision.

    Config fields:
      - left     (required) : left-hand value or '{{field}}' reference
      - operator (required) : comparison operator (see module docstring)
      - right    (required) : right-hand value or '{{field}}' reference

    Returns:
      {
        "branch": "true" | "false",
        "result": bool,
        "input_data": { ...original input_data... }
      }
    """
    left_raw = config.get("left")
    if left_raw is None:
        left_raw = input_data.get("left")
    operator = config.get("operator") or input_data.get("operator")
    right_raw = config.get("right")
    if right_raw is None:
        right_raw = input_data.get("right")

    if operator is None:
        raise ValueError("if_node.branch requires 'operator'")

    left = _resolve_value(left_raw, input_data)
    right = _resolve_value(right_raw, input_data)

    result = _evaluate(left, operator, right)
    branch = "true" if result else "false"

    log.info(
        "if_node.branch",
        left=left,
        operator=operator,
        right=right,
        result=result,
        branch=branch,
    )

    return {
        "branch": branch,
        "result": result,
        "input_data": input_data,
    }
