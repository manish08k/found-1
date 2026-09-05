"""Function integration — execute custom Python expressions in a sandboxed namespace."""
import ast
import io
import contextlib
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

# Safe built-ins available inside sandboxed code
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
    "print": print,
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
    """Walk the AST and raise if any forbidden node types are found."""
    for node in ast.walk(tree):
        if isinstance(node, _FORBIDDEN_AST_NODES):
            raise ValueError(
                f"function.run_code: forbidden statement type '{type(node).__name__}' "
                "— imports and global/nonlocal declarations are not allowed"
            )
        # Block attribute access to dunder methods that could escape sandbox
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError(
                f"function.run_code: access to dunder attribute '{node.attr}' is not allowed"
            )


@register_node("function.run_code")
async def function_run_code(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Safely evaluate a Python expression or script in a sandboxed namespace.

    Config:
        code (str): Python expression or multi-line script.
        The variable `data` is pre-bound to input_data.
    Returns:
        result: the value of `result` variable if set, else None.
        output: any text printed to stdout during execution.
    """
    code = config.get("code") or input_data.get("code", "")

    if not code or not code.strip():
        return {"result": None, "output": ""}

    log.info("function.run_code", code_length=len(code))

    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        raise ValueError(f"function.run_code: syntax error — {exc}") from exc

    _check_ast_safety(tree)

    namespace: dict = {
        "__builtins__": _SAFE_BUILTINS,
        "data": dict(input_data),
        "result": None,
    }

    stdout_capture = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout_capture):
            exec(compile(tree, "<function_node>", "exec"), namespace)  # noqa: S102
    except Exception as exc:
        raise RuntimeError(f"function.run_code: runtime error — {exc}") from exc

    captured_output = stdout_capture.getvalue()
    result = namespace.get("result")

    log.info("function.run_code completed", has_result=result is not None)
    return {"result": result, "output": captured_output}
