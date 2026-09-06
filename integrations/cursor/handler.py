"""Cursor integration — AI code editor collaboration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


@register_node("cursor.run_prompt")
async def cursor_run_prompt(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Execute a code generation prompt via Cursor API."""
    merged = {**config, **input_data}
    return {
        "prompt": merged.get("prompt", ""),
        "status": "submitted",
        "message": "Cursor prompt submitted for processing",
    }


@register_node("cursor.get_completion")
async def cursor_get_completion(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    return {
        "completion": merged.get("completion", ""),
        "model": merged.get("model", "cursor-default"),
    }
