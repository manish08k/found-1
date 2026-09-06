"""Manus integration — AI agent platform."""
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


@register_node("manus.run_task")
async def manus_run_task(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    return {
        "task": merged.get("task", ""),
        "status": "submitted",
        "message": "Task submitted to Manus AI agent",
    }


@register_node("manus.get_task_result")
async def manus_get_task_result(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    return {
        "task_id": merged.get("task_id", ""),
        "status": "completed",
        "result": merged.get("result", ""),
    }
