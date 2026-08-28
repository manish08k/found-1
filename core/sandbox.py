"""
Sandboxed code execution for core.run_code nodes.

Layered defenses:
  1. RestrictedPython compiles the source with attribute-access guards,
     so the classic exec()-escape via __class__/__subclasses__/__globals__
     traversal is rejected at compile time.
  2. Execution happens in a short-lived child process, not the Celery
     worker process — so even a successful escape can't read the
     worker's in-memory decrypted OAuth tokens.
  3. The child process has hard CPU time, memory, file-descriptor,
     process-spawn, and file-write limits, plus sockets disabled, plus
     a wall-clock timeout enforced from the parent.

For real multi-tenant isolation, run this inside a gVisor/Firecracker
microVM or a WASM/Pyodide runtime instead of a bare subprocess — this
is OS-level defense-in-depth, not a hard boundary against a determined
attacker with arbitrary CPython bytecode execution.
"""
import json
import multiprocessing
import resource
import socket

from RestrictedPython import compile_restricted, safe_globals
from RestrictedPython.Eval import default_guarded_getiter
from RestrictedPython.Guards import guarded_iter_unpack_sequence, safer_getattr

CPU_TIME_LIMIT_SECONDS = 5
MEMORY_LIMIT_BYTES = 128 * 1024 * 1024  # 128 MB
WALL_CLOCK_TIMEOUT_SECONDS = 8
MAX_OUTPUT_BYTES = 1 * 1024 * 1024  # 1 MB


def _disable_network() -> None:
    def _blocked(*_a, **_k):
        raise OSError("Network access is disabled inside core.run_code")

    socket.socket = _blocked
    socket.create_connection = _blocked


def _apply_resource_limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_TIME_LIMIT_SECONDS, CPU_TIME_LIMIT_SECONDS))
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT_BYTES, MEMORY_LIMIT_BYTES))
    resource.setrlimit(resource.RLIMIT_NOFILE, (16, 16))
    resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))  # no forking/spawning further procs
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))  # no file writes


def _child_worker(code: str, input_data: dict, conn) -> None:
    try:
        _apply_resource_limits()
        _disable_network()

        restricted_globals = dict(safe_globals)
        restricted_globals.update({
            "__builtins__": safe_globals["__builtins__"],
            "_getattr_": safer_getattr,
            "_getiter_": default_guarded_getiter,
            "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
            "_print_": lambda *a, **k: None,
            "json": json,
        })
        restricted_locals = {"input": input_data, "output": None}

        byte_code = compile_restricted(code, filename="<run_code>", mode="exec")
        exec(byte_code, restricted_globals, restricted_locals)  # noqa: S102

        output = restricted_locals.get("output", input_data)
        payload = json.dumps(output if isinstance(output, dict) else {"output": output})
        if len(payload.encode()) > MAX_OUTPUT_BYTES:
            raise ValueError("run_code output exceeds 1MB limit")
        conn.send(("ok", payload))
    except Exception as exc:  # noqa: BLE001 — must report every failure mode to parent
        conn.send(("error", f"{type(exc).__name__}: {exc}"))
    finally:
        conn.close()


async def run_sandboxed(code: str, input_data: dict) -> dict:
    ctx = multiprocessing.get_context("spawn")
    parent_conn, child_conn = ctx.Pipe()
    proc = ctx.Process(target=_child_worker, args=(code, input_data, child_conn), daemon=True)
    proc.start()
    proc.join(timeout=WALL_CLOCK_TIMEOUT_SECONDS)

    if proc.is_alive():
        proc.terminate()
        proc.join(1)
        if proc.is_alive():
            proc.kill()
        raise RuntimeError(f"run_code timed out after {WALL_CLOCK_TIMEOUT_SECONDS}s")

    if not parent_conn.poll():
        raise RuntimeError(f"run_code crashed (exit code {proc.exitcode})")

    status, payload = parent_conn.recv()
    if status == "error":
        raise RuntimeError(f"run_code error: {payload}")
    return json.loads(payload)
