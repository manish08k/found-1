"""StopAndError integration — halt workflow execution with a descriptive error."""
import structlog
import httpx  # noqa: F401 — standard import kept for consistency

from core.execution_engine import register_node
from oauth.flow import get_credential_data  # noqa: F401 — standard import

log = structlog.get_logger(__name__)


@register_node("stop_and_error.throw")
async def stop_and_error_throw(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Halts the workflow by raising a RuntimeError.
    No HTTP calls are made; no credentials are required.

    config:
      error_message (str): Human-readable message for the error.
      error_type    (str, optional): Short error type label (e.g. "ValidationError").
    """
    error_message = config.get("error_message") or input_data.get("error_message", "Workflow stopped by StopAndError node.")
    error_type = config.get("error_type") or input_data.get("error_type", "WorkflowError")

    log.warning("stop_and_error.throw", error_type=error_type, error_message=error_message)

    formatted = f"[{error_type}] {error_message}" if error_type else error_message
    raise RuntimeError(formatted)
