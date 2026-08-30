"""
Advanced flow-control nodes.

Covers:
  flow.merge, flow.delay, flow.limit_rate, flow.retry_on_error,
  flow.set_variable, flow.get_variable, flow.stop, flow.no_op

Variables are threaded through input_data under the reserved key
'__variables__' so they propagate through the execution graph without
requiring engine-level changes.
"""
import asyncio
import time
from copy import deepcopy
from typing import Any

import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


# ─── Internal StopExecution exception ─────────────────────────────────────────

class StopExecution(Exception):
    """Raised by flow.stop to halt workflow execution immediately."""


# ─── flow.merge ───────────────────────────────────────────────────────────────

@register_node("flow.merge")
async def flow_merge(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Merge outputs from multiple branches.

    In a single-execution-path model the engine calls this node once with
    the accumulated input_data from all converging branches already merged
    by the engine. The node's job is to apply the requested mode strategy
    to the 'branches' list if present, or simply pass through otherwise.

    Config:
        mode: "first" | "all" | "any" (default: "all")
              first — return only the first branch result
              all   — return all branch results as a list
              any   — return all results (synonym for all in sync mode)
    """
    mode = config.get("mode", "all").lower()
    branches = input_data.get("branches")

    if branches is None:
        # No explicit branches key — pass through as-is
        return deepcopy(input_data)

    if not isinstance(branches, list):
        raise ValueError("flow.merge: 'branches' must be a list")

    if mode == "first":
        return branches[0] if branches else {}
    elif mode in ("all", "any"):
        return {"branches": branches, "count": len(branches)}
    else:
        raise ValueError(f"flow.merge: unknown mode '{mode}' — use first/all/any")


# ─── flow.delay ───────────────────────────────────────────────────────────────

@register_node("flow.delay")
async def flow_delay(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Pause execution for a given number of seconds (max 300)."""
    seconds = float(config.get("seconds", 1))
    if seconds < 0:
        raise ValueError("flow.delay: 'seconds' must be non-negative")
    seconds = min(seconds, 300)
    log.info("flow.delay", seconds=seconds)
    await asyncio.sleep(seconds)
    return {**deepcopy(input_data), "__delayed_seconds__": seconds}


# ─── flow.limit_rate ──────────────────────────────────────────────────────────

# Module-level token-bucket state (keyed by workflow node label)
_rate_limit_state: dict[str, dict] = {}


@register_node("flow.limit_rate")
async def flow_limit_rate(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Simple token-bucket rate limiter.

    Config:
        max_per_second: float — allowed calls per second (default: 1)
        bucket_key: str       — identifies this limiter (default: "default")
    """
    max_per_second = float(config.get("max_per_second", 1))
    bucket_key = str(config.get("bucket_key", "default"))

    if max_per_second <= 0:
        raise ValueError("flow.limit_rate: 'max_per_second' must be > 0")

    min_interval = 1.0 / max_per_second
    now = time.monotonic()

    state = _rate_limit_state.setdefault(bucket_key, {"last_call": 0.0})
    elapsed = now - state["last_call"]
    wait = min_interval - elapsed
    if wait > 0:
        await asyncio.sleep(wait)

    _rate_limit_state[bucket_key]["last_call"] = time.monotonic()
    return deepcopy(input_data)


# ─── flow.retry_on_error ─────────────────────────────────────────────────────

@register_node("flow.retry_on_error")
async def flow_retry_on_error(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Retry wrapper — passes input_data through and records retry policy.

    The execution engine is responsible for actual retry logic per node.
    This node decorates the output with retry metadata that the engine
    reads and uses to configure downstream error handling.

    Config:
        max_attempts:  int   — maximum retry attempts (default: 3)
        delay_seconds: float — delay between retries (default: 1)
    """
    max_attempts = int(config.get("max_attempts", 3))
    delay_seconds = float(config.get("delay_seconds", 1))
    if max_attempts < 1:
        raise ValueError("flow.retry_on_error: 'max_attempts' must be >= 1")
    if delay_seconds < 0:
        raise ValueError("flow.retry_on_error: 'delay_seconds' must be >= 0")

    return {
        **deepcopy(input_data),
        "__retry_policy__": {
            "max_attempts": max_attempts,
            "delay_seconds": delay_seconds,
        },
    }


# ─── flow.set_variable ────────────────────────────────────────────────────────

@register_node("flow.set_variable")
async def flow_set_variable(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Set a named workflow variable in the execution context.

    Variables are stored in input_data['__variables__'] so they
    propagate to downstream nodes.
    """
    name = config.get("name") or input_data.get("__set_var_name__")
    value = config.get("value")
    if value is None:
        value = input_data.get("__set_var_value__")
    if not name:
        raise ValueError("flow.set_variable: 'name' is required")

    result = deepcopy(input_data)
    variables: dict = result.setdefault("__variables__", {})
    variables[name] = value
    log.debug("flow.set_variable", name=name)
    return result


# ─── flow.get_variable ────────────────────────────────────────────────────────

@register_node("flow.get_variable")
async def flow_get_variable(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Retrieve a previously set workflow variable from execution context.

    Returns the variable value alongside the full input_data.
    """
    name = config.get("name")
    if not name:
        raise ValueError("flow.get_variable: 'name' is required")

    variables: dict = input_data.get("__variables__", {})
    if name not in variables:
        default = config.get("default")
        if default is None and config.get("required", False):
            raise ValueError(f"flow.get_variable: variable '{name}' has not been set")
        value = default
    else:
        value = variables[name]

    result = deepcopy(input_data)
    result["value"] = value
    result["variable_name"] = name
    return result


# ─── flow.stop ────────────────────────────────────────────────────────────────

@register_node("flow.stop")
async def flow_stop(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Stop workflow execution immediately."""
    reason = config.get("reason") or input_data.get("reason", "flow.stop node reached")
    log.info("flow.stop", reason=reason)
    raise StopExecution(reason)


# ─── flow.no_op ───────────────────────────────────────────────────────────────

@register_node("flow.no_op")
async def flow_no_op(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Pass-through node — returns input unchanged (useful for debugging)."""
    return deepcopy(input_data)
