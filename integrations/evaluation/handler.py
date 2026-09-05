"""
Evaluation integration — expression and condition evaluation.

Provides safe condition checking and expression evaluation without
credentials or external HTTP calls.

Supported operators for evaluate_condition:
  eq, ne, gt, gte, lt, lte, contains, not_contains, starts_with, ends_with,
  is_empty, is_not_empty, in, not_in, regex
"""
import ast
import operator
import re
import structlog
import httpx  # noqa: F401 – kept for platform consistency

from core.execution_engine import register_node
from oauth.flow import get_credential_data  # noqa: F401 – kept for platform consistency

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Safe expression evaluation helpers
# ---------------------------------------------------------------------------

_SAFE_NODES = {
    ast.Expression, ast.BoolOp, ast.BinOp, ast.UnaryOp,
    ast.Compare, ast.Call, ast.IfExp, ast.Attribute,
    # Literals
    ast.Constant, ast.List, ast.Tuple, ast.Set, ast.Dict,
    # Operators
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.UAdd, ast.USub, ast.Not, ast.Invert,
    ast.And, ast.Or,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.Is, ast.IsNot, ast.In, ast.NotIn,
    # Name references are allowed — we restrict via the eval namespace
    ast.Name, ast.Load,
}


def _is_safe_ast(node: ast.AST) -> bool:
    """Recursively check that an AST only contains safe node types."""
    if type(node) not in _SAFE_NODES:
        return False
    return all(_is_safe_ast(child) for child in ast.iter_child_nodes(node))


def _safe_eval(expr: str, variables: dict | None = None) -> object:
    """
    Evaluate a simple arithmetic / boolean / string expression safely.

    Raises ValueError if the expression is deemed unsafe or fails to parse.
    """
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Invalid expression syntax: {exc}") from exc

    if not _is_safe_ast(tree):
        raise ValueError("Expression contains disallowed constructs")

    # Restricted builtins namespace
    safe_builtins = {
        "abs": abs, "round": round, "min": min, "max": max,
        "len": len, "str": str, "int": int, "float": float,
        "bool": bool, "list": list, "dict": dict, "tuple": tuple,
        "True": True, "False": False, "None": None,
    }
    namespace = {**safe_builtins, **(variables or {})}
    try:
        return eval(compile(tree, "<string>", "eval"), {"__builtins__": {}}, namespace)  # noqa: S307
    except Exception as exc:
        raise ValueError(f"Expression evaluation error: {exc}") from exc


# ---------------------------------------------------------------------------
# Condition operator dispatch
# ---------------------------------------------------------------------------

def _coerce(value: object, other: object) -> tuple:
    """Try to coerce value to the type of other for numeric comparisons."""
    if isinstance(other, (int, float)) and isinstance(value, str):
        try:
            return float(value), other
        except ValueError:
            pass
    return value, other


def _apply_operator(left: object, op: str, right: object) -> bool:
    op = op.strip().lower().replace("-", "_").replace(" ", "_")

    if op in ("eq", "==", "equals"):
        return left == right
    if op in ("ne", "!=", "not_equals"):
        return left != right

    l, r = _coerce(left, right)
    if op in ("gt", ">"):
        return operator.gt(l, r)
    if op in ("gte", ">="):
        return operator.ge(l, r)
    if op in ("lt", "<"):
        return operator.lt(l, r)
    if op in ("lte", "<="):
        return operator.le(l, r)

    # String ops
    left_str = str(left)
    right_str = str(right)
    if op == "contains":
        return right_str in left_str
    if op == "not_contains":
        return right_str not in left_str
    if op == "starts_with":
        return left_str.startswith(right_str)
    if op == "ends_with":
        return left_str.endswith(right_str)
    if op == "is_empty":
        return not left or (isinstance(left, str) and not left.strip())
    if op == "is_not_empty":
        return bool(left) and (not isinstance(left, str) or bool(left.strip()))

    # Collection ops
    if op == "in":
        return left in (right if isinstance(right, (list, tuple, set)) else [right])
    if op == "not_in":
        return left not in (right if isinstance(right, (list, tuple, set)) else [right])

    # Regex
    if op in ("regex", "matches"):
        return bool(re.search(str(right), str(left)))

    raise ValueError(f"Unknown operator: '{op}'")


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@register_node("evaluation.evaluate_condition")
async def evaluate_condition(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Evaluate a binary condition and return a boolean result.

    Config / input keys:
      - left_value  (any)  : Left-hand operand.
      - operator    (str)  : Comparison operator (see module docstring).
      - right_value (any)  : Right-hand operand.

    Returns:
      {
        "result"      : bool,
        "left_value"  : any,
        "operator"    : str,
        "right_value" : any,
        "branch"      : "true" | "false"
      }
    """
    left = config.get("left_value") if "left_value" in config else input_data.get("left_value")
    op = str(config.get("operator") or input_data.get("operator", "eq"))
    right = config.get("right_value") if "right_value" in config else input_data.get("right_value")

    log.info("evaluation.evaluate_condition", operator=op)

    try:
        result = _apply_operator(left, op, right)
    except ValueError as exc:
        raise ValueError(f"evaluation.evaluate_condition: {exc}") from exc

    return {
        "result": result,
        "left_value": left,
        "operator": op,
        "right_value": right,
        "branch": "true" if result else "false",
    }


@register_node("evaluation.run_expression")
async def run_expression(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Safely evaluate a mathematical or boolean expression string.

    Variables from `variables` config/input are injected into the expression
    namespace.  Complex Python constructs (imports, function definitions, etc.)
    are rejected.

    Config / input keys:
      - expression (str)  : Expression to evaluate, e.g. "price * 1.2 + tax".
      - variables  (dict) : Named values injected into the expression scope.

    Returns:
      {
        "expression" : str,
        "result"     : any,
        "result_type": str  (Python type name)
      }
    """
    expression = str(config.get("expression") or input_data.get("expression", ""))
    variables = config.get("variables") or input_data.get("variables", {})

    if not expression.strip():
        raise ValueError("evaluation.run_expression requires a non-empty 'expression'")

    if not isinstance(variables, dict):
        variables = {}

    log.info("evaluation.run_expression", expression=expression)

    result = _safe_eval(expression, variables)

    return {
        "expression": expression,
        "result": result,
        "result_type": type(result).__name__,
    }


@register_node("evaluation.switch")
async def switch(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Evaluate multiple conditions and return the label of the first matching case.

    Config / input keys:
      - value   (any)         : The value to test.
      - cases   (list[dict])  : List of { "label": str, "operator": str,
                                "match": any } objects, tested in order.
      - default (str)         : Label to return if no case matches.
                                Default "default".

    Returns:
      {
        "matched_label"   : str,
        "matched_index"   : int | None,
        "value"           : any,
        "is_default"      : bool
      }
    """
    value = config.get("value") if "value" in config else input_data.get("value")
    cases: list = config.get("cases") or input_data.get("cases", [])
    default_label: str = config.get("default") or input_data.get("default", "default")

    log.info("evaluation.switch", case_count=len(cases))

    for idx, case in enumerate(cases):
        op = str(case.get("operator", "eq"))
        match_val = case.get("match")
        label = str(case.get("label", f"case_{idx}"))
        try:
            if _apply_operator(value, op, match_val):
                return {
                    "matched_label": label,
                    "matched_index": idx,
                    "value": value,
                    "is_default": False,
                }
        except ValueError:
            continue

    return {
        "matched_label": default_label,
        "matched_index": None,
        "value": value,
        "is_default": True,
    }
