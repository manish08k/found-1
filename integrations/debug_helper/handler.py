"""DebugHelper integration — utility nodes for workflow debugging and error simulation."""
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


@register_node("debug_helper.throw_error")
async def debug_helper_throw_error(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Raise a ValueError with the configured error message.

    Useful for testing error-handling branches in a workflow.

    config:
      error_message — the message to include in the ValueError
    """
    message = config.get("error_message") or input_data.get("error_message") or "DebugHelper: intentional error"
    log.info("debug_helper.throw_error", message=message)
    raise ValueError(message)


@register_node("debug_helper.out_of_memory")
async def debug_helper_out_of_memory(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Simulate an out-of-memory condition by raising a MemoryError.

    Useful for testing OOM handling in a workflow.

    config:
      error_message — optional custom message (defaults to a generic OOM message)
    """
    message = (
        config.get("error_message")
        or input_data.get("error_message")
        or "DebugHelper: simulated out-of-memory error"
    )
    log.info("debug_helper.out_of_memory", message=message)
    raise MemoryError(message)


@register_node("debug_helper.do_nothing")
async def debug_helper_do_nothing(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """No-op node — passes input_data through unchanged.

    Useful as a placeholder or for flow-control testing.
    """
    log.info("debug_helper.do_nothing")
    return dict(input_data)
