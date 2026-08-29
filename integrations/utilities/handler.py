"""
Utility nodes — workflow utilities for variable management, conditional logic,
and custom functions. These mirror Flowise's utilities category.

Nodes:
  - utility.set_variable      — SetVariable: set a named variable in state
  - utility.get_variable      — GetVariable: retrieve a named variable
  - utility.if_else           — IfElseFunction: conditional branching
  - utility.custom_function   — CustomFunction: execute user-defined Python
  - utility.sticky_note       — StickyNote: passthrough annotation node
"""
import json
import re
import math

from core.execution_engine import register_node

import structlog

log = structlog.get_logger(__name__)


def _render(template: str, data: dict) -> str:
    """Resolve {{ field }} templates against data dict."""
    if not isinstance(template, str):
        return template

    def repl(m):
        path = m.group(1).strip().split(".")
        val = data
        for p in path:
            val = val.get(p) if isinstance(val, dict) else None
        return "" if val is None else (val if isinstance(val, str) else json.dumps(val))

    return re.sub(r"\{\{\s*([\w\.]+)\s*\}\}", repl, template)


def _safe_eval(expr: str, context: dict) -> object:
    """Safely evaluate a simple expression with restricted builtins."""
    safe_builtins = {
        "True": True, "False": False, "None": None,
        "len": len, "str": str, "int": int, "float": float, "bool": bool,
        "list": list, "dict": dict, "tuple": tuple, "set": set,
        "abs": abs, "round": round, "min": min, "max": max, "sum": sum,
        "sorted": sorted, "reversed": reversed, "enumerate": enumerate,
        "zip": zip, "any": any, "all": all, "isinstance": isinstance,
        "math": math,
    }
    return eval(expr, {"__builtins__": safe_builtins}, context)  # noqa: S307


# ─── SetVariable ──────────────────────────────────────────────────────────────

@register_node("utility.set_variable")
async def utility_set_variable(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    SetVariable: sets one or more named variables in the workflow state.
    The output contains all input_data plus the new variables.

    config:
      - variable_name: name of the variable to set
      - value: the value (supports {{ }} templates and JSON)
      - variables: dict of {name: value} for setting multiple at once
    """
    result = dict(input_data)

    # Handle multiple variables at once
    variables = config.get("variables") or {}
    for name, val in variables.items():
        if isinstance(val, str):
            rendered = _render(val, input_data)
            # Try to parse as JSON for complex types
            try:
                result[name] = json.loads(rendered)
            except (json.JSONDecodeError, ValueError):
                result[name] = rendered
        else:
            result[name] = val

    # Handle single variable
    var_name = config.get("variable_name") or config.get("name")
    var_value = config.get("value")

    if var_name:
        if isinstance(var_value, str):
            rendered = _render(var_value, input_data)
            try:
                result[var_name] = json.loads(rendered)
            except (json.JSONDecodeError, ValueError):
                result[var_name] = rendered
        elif var_value is not None:
            result[var_name] = var_value
        else:
            # Get value from input_data using source key
            source_key = config.get("source_key")
            if source_key:
                result[var_name] = input_data.get(source_key)

    return result


# ─── GetVariable ──────────────────────────────────────────────────────────────

@register_node("utility.get_variable")
async def utility_get_variable(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    GetVariable: retrieves a named variable from the workflow state.

    config:
      - variable_name: name of the variable to retrieve
      - default: default value if variable not found
      - output_key: key to put the value under (default: same as variable_name)
    """
    var_name = config.get("variable_name") or config.get("name")
    if not var_name:
        raise ValueError("utility.get_variable requires 'variable_name'")

    default = config.get("default")
    output_key = config.get("output_key") or var_name

    value = input_data.get(var_name, default)

    return {
        **input_data,
        output_key: value,
        "_retrieved_variable": var_name,
        "_retrieved_value": value,
    }


# ─── IfElseFunction ──────────────────────────────────────────────────────────

@register_node("utility.if_else")
async def utility_if_else(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    IfElseFunction: evaluates a condition and returns one of two values.
    Supports template expressions and safe Python evaluation.

    config:
      - condition: Python expression evaluated against input_data variables
                   OR a dict with {field, operator, value} for simple conditions
      - true_value: value/template to return if condition is true
      - false_value: value/template to return if condition is false
      - output_key: key to store the result (default: "result")
    """
    output_key = config.get("output_key", "result")
    condition = config.get("condition", "False")
    true_value = config.get("true_value", True)
    false_value = config.get("false_value", False)

    # Evaluate the condition
    condition_met = False
    try:
        if isinstance(condition, dict):
            # Structured condition: {field, operator, value}
            field = condition.get("field")
            operator = condition.get("operator", "equals")
            cmp_value = condition.get("value")
            item_val = input_data.get(field) if field else None

            op_map = {
                "equals": lambda a, b: a == b,
                "not_equals": lambda a, b: a != b,
                "contains": lambda a, b: str(b) in str(a or ""),
                "not_contains": lambda a, b: str(b) not in str(a or ""),
                "greater_than": lambda a, b: float(a or 0) > float(b),
                "less_than": lambda a, b: float(a or 0) < float(b),
                "is_empty": lambda a, b: not a,
                "is_not_empty": lambda a, b: bool(a),
                "is_true": lambda a, b: bool(a),
                "is_false": lambda a, b: not bool(a),
                "in": lambda a, b: a in (b if isinstance(b, list) else [b]),
                "regex": lambda a, b: bool(re.search(str(b), str(a or ""))),
            }
            fn = op_map.get(operator, lambda a, b: False)
            condition_met = fn(item_val, cmp_value)
        elif isinstance(condition, str):
            # Python expression — render templates first
            rendered_condition = _render(condition, input_data)
            try:
                condition_met = bool(_safe_eval(rendered_condition, dict(input_data)))
            except Exception:
                # Fallback: check if rendered string is truthy
                condition_met = rendered_condition.lower() not in ("false", "0", "", "none", "null")
        else:
            condition_met = bool(condition)
    except Exception as e:
        log.warning("if_else_condition_error", error=str(e))
        condition_met = False

    # Resolve the output value
    selected = true_value if condition_met else false_value
    if isinstance(selected, str):
        selected = _render(selected, input_data)
        try:
            selected = json.loads(selected)
        except (json.JSONDecodeError, ValueError):
            pass

    return {
        **input_data,
        output_key: selected,
        "branch": "true" if condition_met else "false",
        "condition_met": condition_met,
    }


# ─── CustomFunction ──────────────────────────────────────────────────────────

@register_node("utility.custom_function")
async def utility_custom_function(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    CustomFunction: executes user-defined Python code in a sandboxed environment.
    The function receives `input_data` as a dict and must return a dict.

    config:
      - code: Python function body as a string. The function must be named
              according to `function_name` (default: 'execute') and accept
              `input_data: dict` as its only parameter.
      - function_name: name of the function to call (default: 'execute')
      - timeout: max execution seconds (default: 10)

    Example code:
      def execute(input_data):
          return {"doubled": input_data.get("number", 0) * 2}
    """
    import asyncio
    import concurrent.futures

    code = config.get("code", "")
    function_name = config.get("function_name", "execute")
    timeout = float(config.get("timeout", 10))

    if not code:
        return input_data

    # Safe builtins
    safe_globals = {
        "__builtins__": {
            "print": print,
            "len": len, "str": str, "int": int, "float": float, "bool": bool,
            "list": list, "dict": dict, "tuple": tuple, "set": set,
            "range": range, "enumerate": enumerate, "zip": zip,
            "map": map, "filter": filter,
            "sorted": sorted, "reversed": reversed,
            "min": min, "max": max, "sum": sum, "abs": abs, "round": round,
            "any": any, "all": all, "isinstance": isinstance, "issubclass": issubclass,
            "type": type, "hasattr": hasattr, "getattr": getattr,
            "ValueError": ValueError, "TypeError": TypeError, "KeyError": KeyError,
            "Exception": Exception,
            "True": True, "False": False, "None": None,
        },
        "json": json,
        "re": re,
        "math": math,
    }

    def _run():
        local_ns = {}
        exec(code, safe_globals, local_ns)  # noqa: S102
        if function_name not in local_ns:
            raise ValueError(f"Function '{function_name}' not found in code")
        fn = local_ns[function_name]
        result = fn(dict(input_data))
        if not isinstance(result, dict):
            result = {"result": result}
        return result

    try:
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = await asyncio.wait_for(
                loop.run_in_executor(pool, _run),
                timeout=timeout,
            )
        return {**input_data, **result}
    except asyncio.TimeoutError:
        raise TimeoutError(f"utility.custom_function timed out after {timeout}s")
    except Exception as e:
        raise RuntimeError(f"utility.custom_function error: {e}") from e


# ─── StickyNote ──────────────────────────────────────────────────────────────

@register_node("utility.sticky_note")
async def utility_sticky_note(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    StickyNote: a no-op passthrough node used for canvas annotations.
    Does not transform data — simply passes input through unchanged.

    config:
      - content: annotation text (informational only, not executed)
      - color: note color for UI display
    """
    # Pure passthrough — this node exists only for canvas annotation
    return dict(input_data)
