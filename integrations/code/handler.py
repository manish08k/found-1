"""
Code execution nodes — safely run user-supplied code snippets.

Covers:
  code.python     — restricted exec() with AST import validation
  code.javascript — subprocess calling `node -e` with JSON I/O
  code.expression — single Python expression via eval()
  code.template   — Jinja2 template rendering
"""
import ast
import builtins
import contextlib
import io
import json
import math
import re
import subprocess
import textwrap
from datetime import datetime, date, timedelta
from typing import Any

import structlog
from jinja2 import Environment, StrictUndefined, TemplateSyntaxError

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


# ─── AST import checker ───────────────────────────────────────────────────────

_FORBIDDEN_AST_NODES = (ast.Import, ast.ImportFrom)
_FORBIDDEN_NAMES = frozenset({
    "__import__", "__builtins__", "open", "exec", "eval",
    "compile", "globals", "locals", "vars", "dir",
    "getattr", "setattr", "delattr", "hasattr",
    "breakpoint", "input",
})


def _validate_no_imports(code: str) -> None:
    """Raise ValueError if code contains import statements or forbidden names."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise ValueError(f"code.python: syntax error — {exc}") from exc

    for node in ast.walk(tree):
        if isinstance(node, _FORBIDDEN_AST_NODES):
            raise ValueError("code.python: import statements are not allowed")
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            raise ValueError(f"code.python: use of '{node.id}' is not allowed")
        if isinstance(node, ast.Attribute) and node.attr in {"__class__", "__subclasses__", "__mro__"}:
            raise ValueError(f"code.python: access to '{node.attr}' is not allowed")


_SAFE_BUILTINS = {
    name: getattr(builtins, name)
    for name in (
        "abs", "all", "any", "bool", "bytes", "chr", "dict", "divmod",
        "enumerate", "filter", "float", "format", "frozenset", "hex",
        "int", "isinstance", "issubclass", "iter", "len", "list", "map",
        "max", "min", "next", "oct", "ord", "pow", "print", "range",
        "repr", "reversed", "round", "set", "slice", "sorted", "str",
        "sum", "tuple", "type", "zip",
        "True", "False", "None",
        "ValueError", "TypeError", "KeyError", "IndexError", "AttributeError",
        "RuntimeError", "StopIteration", "Exception",
    )
}


# ─── code.python ─────────────────────────────────────────────────────────────

@register_node("code.python")
async def code_python(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Execute a Python code snippet in a sandboxed context."""
    import asyncio
    import concurrent.futures

    code_str = config.get("code")
    if not code_str:
        raise ValueError("code.python: 'code' is required")

    timeout_seconds = float(config.get("timeout_seconds", 10))
    if timeout_seconds > 300:
        timeout_seconds = 300

    _validate_no_imports(code_str)

    def _run() -> Any:
        stdout_buf = io.StringIO()
        ns: dict = {
            "__builtins__": _SAFE_BUILTINS,
            "data": input_data,
            "json": json,
            "math": math,
            "re": re,
            "datetime": datetime,
            "date": date,
            "timedelta": timedelta,
            "result": None,
        }
        with contextlib.redirect_stdout(stdout_buf):
            exec(compile(code_str, "<code.python>", "exec"), ns)  # noqa: S102
        return ns.get("result"), stdout_buf.getvalue()

    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        try:
            result, stdout = await asyncio.wait_for(
                loop.run_in_executor(pool, _run),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            raise ValueError(f"code.python: execution timed out after {timeout_seconds}s")
        except Exception as exc:
            raise ValueError(f"code.python: execution error — {exc}") from exc

    return {"result": result, "stdout": stdout}


# ─── code.javascript ─────────────────────────────────────────────────────────

@register_node("code.javascript")
async def code_javascript(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Execute JavaScript via subprocess calling `node -e`. I/O via JSON."""
    import asyncio

    code_str = config.get("code")
    if not code_str:
        raise ValueError("code.javascript: 'code' is required")

    timeout_seconds = float(config.get("timeout_seconds", 10))
    if timeout_seconds > 300:
        timeout_seconds = 300

    # Wrap user code so input arrives via process.stdin and output via stdout
    wrapper = textwrap.dedent(f"""
        const chunks = [];
        process.stdin.on('data', c => chunks.push(c));
        process.stdin.on('end', () => {{
            const data = JSON.parse(chunks.join(''));
            let result = null;
            (function() {{
                {code_str}
            }})();
            process.stdout.write(JSON.stringify({{ result }}));
        }});
    """)

    input_bytes = json.dumps(input_data).encode()
    try:
        proc = await asyncio.create_subprocess_exec(
            "node", "-e", wrapper,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=input_bytes),
            timeout=timeout_seconds,
        )
    except FileNotFoundError:
        raise ValueError("code.javascript: 'node' executable not found in PATH")
    except asyncio.TimeoutError:
        proc.kill()
        raise ValueError(f"code.javascript: execution timed out after {timeout_seconds}s")

    if proc.returncode != 0:
        err = stderr.decode(errors="replace")[:500]
        raise ValueError(f"code.javascript: runtime error — {err}")

    try:
        output = json.loads(stdout.decode())
    except json.JSONDecodeError as exc:
        raise ValueError(f"code.javascript: invalid JSON output — {exc}") from exc

    return output


# ─── code.expression ─────────────────────────────────────────────────────────

@register_node("code.expression")
async def code_expression(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Evaluate a single Python expression safely."""
    expression = config.get("expression")
    if not expression:
        raise ValueError("code.expression: 'expression' is required")

    # Validate no imports
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"code.expression: syntax error — {exc}") from exc

    for node in ast.walk(tree):
        if isinstance(node, _FORBIDDEN_AST_NODES):
            raise ValueError("code.expression: import statements are not allowed")

    safe_globals: dict = {
        "__builtins__": _SAFE_BUILTINS,
        "data": input_data,
        "math": math,
        "json": json,
        "re": re,
        "datetime": datetime,
        "date": date,
        "timedelta": timedelta,
    }
    try:
        result = eval(compile(tree, "<code.expression>", "eval"), safe_globals)  # noqa: S307
    except Exception as exc:
        raise ValueError(f"code.expression: evaluation error — {exc}") from exc

    return {"result": result}


# ─── code.template ───────────────────────────────────────────────────────────

@register_node("code.template")
async def code_template(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Render a Jinja2 template with input_data as context."""
    template_str = config.get("template")
    if not template_str:
        raise ValueError("code.template: 'template' is required")

    env = Environment(
        undefined=StrictUndefined,
        autoescape=config.get("autoescape", False),
    )
    try:
        tmpl = env.from_string(template_str)
        rendered = tmpl.render(**input_data)
    except TemplateSyntaxError as exc:
        raise ValueError(f"code.template: template syntax error — {exc}") from exc
    except Exception as exc:
        raise ValueError(f"code.template: render error — {exc}") from exc

    output_field = config.get("output_field", "output")
    return {output_field: rendered}
