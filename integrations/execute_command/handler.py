"""
ExecuteCommand integration — run shell commands asynchronously.

Executes arbitrary shell commands in a subprocess and returns stdout, stderr,
return code, and a success flag.

SECURITY NOTES:
  - The `command` field must be non-empty.
  - Timeout is capped at 120 seconds to prevent runaway processes.
  - This node should only be available in trusted, self-hosted environments.
    Platform administrators should gate access via RBAC before enabling.

No credentials or external HTTP calls are required.
"""
import asyncio
import shlex
import structlog
import httpx  # noqa: F401 – kept for platform consistency

from core.execution_engine import register_node
from oauth.flow import get_credential_data  # noqa: F401 – kept for platform consistency

log = structlog.get_logger(__name__)

_MAX_TIMEOUT = 120
_MAX_OUTPUT_BYTES = 10 * 1024 * 1024  # 10 MB output cap


@register_node("execute_command.run")
async def run_command(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Execute a shell command and return its output.

    Config / input keys:
      - command     (str)  : Required. Shell command to run.
      - timeout     (int)  : Seconds to wait before killing the process.
                             Default 30, max 120.
      - cwd         (str)  : Working directory for the command. Default None
                             (inherits platform process CWD).
      - env         (dict) : Extra environment variables to merge in.
      - shell       (bool) : Run via shell (True) or exec directly (False).
                             Default True.

    Returns:
      {
        "stdout"      : str,
        "stderr"      : str,
        "return_code" : int,
        "success"     : bool,
        "command"     : str,
        "timed_out"   : bool
      }
    """
    command: str = str(config.get("command") or input_data.get("command", "")).strip()
    if not command:
        raise ValueError("execute_command.run requires a non-empty 'command'")

    timeout_raw = config.get("timeout") or input_data.get("timeout", 30)
    timeout = min(int(timeout_raw), _MAX_TIMEOUT)
    cwd = config.get("cwd") or input_data.get("cwd") or None
    extra_env = config.get("env") or input_data.get("env") or {}
    use_shell = str(config.get("shell") or input_data.get("shell", "true")).lower() not in ("false", "0", "no")

    if extra_env and not isinstance(extra_env, dict):
        extra_env = {}

    log.info(
        "execute_command.run",
        command=command[:200],
        timeout=timeout,
        cwd=cwd,
    )

    import os
    env = {**os.environ, **extra_env} if extra_env else None

    timed_out = False
    try:
        if use_shell:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )
        else:
            args = shlex.split(command)
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=float(timeout)
            )
        except asyncio.TimeoutError:
            timed_out = True
            try:
                proc.kill()
                await proc.communicate()
            except Exception:
                pass
            log.warning("execute_command.run timed out", command=command[:200], timeout=timeout)
            return {
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds",
                "return_code": -1,
                "success": False,
                "command": command,
                "timed_out": True,
            }

    except FileNotFoundError as exc:
        raise ValueError(f"execute_command.run: command not found — {exc}") from exc

    stdout = stdout_bytes[:_MAX_OUTPUT_BYTES].decode(errors="replace") if stdout_bytes else ""
    stderr = stderr_bytes[:_MAX_OUTPUT_BYTES].decode(errors="replace") if stderr_bytes else ""
    return_code = proc.returncode if proc.returncode is not None else -1
    success = return_code == 0

    log.info(
        "execute_command.run finished",
        return_code=return_code,
        stdout_len=len(stdout),
        stderr_len=len(stderr),
    )

    return {
        "stdout": stdout,
        "stderr": stderr,
        "return_code": return_code,
        "success": success,
        "command": command,
        "timed_out": timed_out,
    }


@register_node("execute_command.run_script")
async def run_script(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Write a multi-line script to a temp file and execute it.

    Config / input keys:
      - script      (str)  : Required. Multi-line script body.
      - interpreter (str)  : Interpreter to use. Default "/bin/bash".
      - timeout     (int)  : Seconds to wait. Default 30, max 120.
      - cwd         (str)  : Working directory.
      - env         (dict) : Extra environment variables.

    Returns:
      { "stdout", "stderr", "return_code", "success", "timed_out" }
    """
    script: str = str(config.get("script") or input_data.get("script", "")).strip()
    if not script:
        raise ValueError("execute_command.run_script requires a non-empty 'script'")

    interpreter = str(config.get("interpreter") or input_data.get("interpreter", "/bin/bash"))
    timeout_raw = config.get("timeout") or input_data.get("timeout", 30)
    timeout = min(int(timeout_raw), _MAX_TIMEOUT)
    cwd = config.get("cwd") or input_data.get("cwd") or None
    extra_env = config.get("env") or input_data.get("env") or {}

    import os
    import tempfile

    env = {**os.environ, **extra_env} if extra_env and isinstance(extra_env, dict) else None

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".sh", delete=False, prefix="exec_cmd_"
    ) as tmp:
        tmp.write(script)
        tmp_path = tmp.name

    os.chmod(tmp_path, 0o700)

    log.info("execute_command.run_script", interpreter=interpreter, timeout=timeout, script_len=len(script))

    timed_out = False
    try:
        proc = await asyncio.create_subprocess_exec(
            interpreter,
            tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=float(timeout)
            )
        except asyncio.TimeoutError:
            timed_out = True
            try:
                proc.kill()
                await proc.communicate()
            except Exception:
                pass
            return {
                "stdout": "",
                "stderr": f"Script timed out after {timeout} seconds",
                "return_code": -1,
                "success": False,
                "timed_out": True,
            }
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    stdout = stdout_bytes[:_MAX_OUTPUT_BYTES].decode(errors="replace") if stdout_bytes else ""
    stderr = stderr_bytes[:_MAX_OUTPUT_BYTES].decode(errors="replace") if stderr_bytes else ""
    return_code = proc.returncode if proc.returncode is not None else -1

    return {
        "stdout": stdout,
        "stderr": stderr,
        "return_code": return_code,
        "success": return_code == 0,
        "timed_out": timed_out,
    }
