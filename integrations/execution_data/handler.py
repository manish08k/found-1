"""ExecutionData integration — access workflow execution metadata."""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


def _get_execution_meta(input_data: dict) -> dict:
    """Extract the __execution__ context block from input_data."""
    return input_data.get("__execution__", {})


@register_node("execution_data.get_execution_id")
async def execution_data_get_execution_id(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Return the current execution ID from workflow context."""
    meta = _get_execution_meta(input_data)
    execution_id = meta.get("execution_id")

    log.info("execution_data.get_execution_id", execution_id=execution_id)
    return {"execution_id": execution_id}


@register_node("execution_data.get_workflow_id")
async def execution_data_get_workflow_id(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Return the current workflow ID from workflow context."""
    meta = _get_execution_meta(input_data)
    workflow_id = meta.get("workflow_id")

    log.info("execution_data.get_workflow_id", workflow_id=workflow_id)
    return {"workflow_id": workflow_id}


@register_node("execution_data.get_start_time")
async def execution_data_get_start_time(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Return the workflow execution start time from workflow context."""
    meta = _get_execution_meta(input_data)
    start_time = meta.get("start_time")

    log.info("execution_data.get_start_time", start_time=start_time)
    return {"start_time": start_time}
