"""FunctionItem integration — execute a Python expression for each item in a list."""
import ast
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

# Safe built-ins for per-item evaluation (same policy as function integration)
_SAFE_BUILTINS = {
    "len": len,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "set": set,
    "range": range,
    "enumerate": enumerate,
    "zip": zip,
    "map": map,
    "filter": filter,
    "sorted": sorted,
    "reversed": reversed,
    "sum": sum,
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
    "isinstance": isinstance,
    "type": type,
    "repr": repr,
    "hasattr": hasattr,
    "getattr": getattr,
    "any": any,
    "all": all,
}

_FORBIDDEN_AST_NODES = (
    ast.Import,
    ast.ImportFrom,
    ast.Global,
    ast.Nonlocal,
)


def _check_ast_safety(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(node, _FORBIDDEN_AST_NODES):
            raise ValueError(
                f"function_item: forbidden statement '{type(node).__name__}' — imports not allowed"
            )
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError(
                f"function_item: dunder attribute '{node.attr}' access is not allowed"
            )


def _safe_eval_expression(expression: str, item, index: int):
    """Evaluate a Python expression with `item` and `index` in scope."""
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"function_item: invalid expression syntax — {exc}") from exc

    _check_ast_safety(tree)

    namespace = {
        "__builtins__": _SAFE_BUILTINS,
        "item": item,
        "index": index,
        "i": index,
    }
    try:
        return eval(compile(tree, "<function_item>", "eval"), namespace)  # noqa: S307
    except Exception as exc:
        raise RuntimeError(f"function_item: runtime error at index {index} — {exc}") from exc


@register_node("function_item.process_items")
async def function_item_process_items(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Apply a Python expression to each item in a list.

    Config:
        expression (str): Python expression using `item` (current element) and `index` / `i`.
        items (list): the list to process — falls back to input_data["items"].
    Returns:
        items: list of processed results.
        count: number of items processed.
    """
    expression = config.get("expression") or input_data.get("expression", "item")
    items = config.get("items") if "items" in config else input_data.get("items", [])

    if not isinstance(items, list):
        raise TypeError(f"function_item.process_items: 'items' must be a list, got {type(items).__name__}")

    log.info("function_item.process_items", expression=expression, item_count=len(items))

    processed = [_safe_eval_expression(expression, item, idx) for idx, item in enumerate(items)]

    log.info("function_item.process_items completed", processed_count=len(processed))
    return {"items": processed, "count": len(processed)}
