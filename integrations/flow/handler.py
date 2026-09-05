"""Flow integration — general flow control nodes."""
import asyncio
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_MAX_WAIT_SECONDS = 300


@register_node("flow.no_op")
async def flow_no_op(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Pass-through node — returns input_data unchanged."""
    log.info("flow.no_op")
    return dict(input_data)


@register_node("flow.wait")
async def flow_wait(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Sleep for a given number of seconds (capped at 300s)."""
    seconds = float(config.get("seconds") or input_data.get("seconds", 1))
    seconds = min(seconds, _MAX_WAIT_SECONDS)

    log.info("flow.wait", seconds=seconds)
    await asyncio.sleep(seconds)

    return {"waited_seconds": seconds}


@register_node("flow.stop")
async def flow_stop(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Stop workflow execution with an optional message."""
    message = config.get("message") or input_data.get("message", "Workflow stopped")

    log.info("flow.stop", message=message)
    raise StopIteration(message)
