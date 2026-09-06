"""Copy.ai workflow automation integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

COPY_AI_BASE = "https://api.copy.ai/api"


@register_node("copy_ai.run_workflow")
async def copy_ai_run_workflow(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Run a Copy.ai workflow with given inputs.

    config/input_data:
      api_key     — Copy.ai API key
      workflow_id — ID of the workflow to run
      inputs      — dict of workflow input variables
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    workflow_id = merged.get("workflow_id", "")
    if not workflow_id:
        raise ValueError("workflow_id is required")

    payload = {
        "workflowId": workflow_id,
        "startVariables": merged.get("inputs", {}),
        "metadata": merged.get("metadata", {}),
    }

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{COPY_AI_BASE}/workflow/{workflow_id}/run",
            headers={"x-copy-ai-api-key": api_key, "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        result = r.json()

    log.info("copy_ai.run_workflow", workflow_id=workflow_id)
    return result


@register_node("copy_ai.list_workflows")
async def copy_ai_list_workflows(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Copy.ai workflows.

    config/input_data:
      api_key — Copy.ai API key
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{COPY_AI_BASE}/workflow",
            headers={"x-copy-ai-api-key": api_key},
        )
        r.raise_for_status()
        result = r.json()

    log.info("copy_ai.list_workflows")
    return result


@register_node("copy_ai.get_run_result")
async def copy_ai_get_run_result(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get the result of a Copy.ai workflow run.

    config/input_data:
      api_key     — Copy.ai API key
      workflow_id — ID of the workflow
      run_id      — ID of the run to retrieve
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    workflow_id = merged.get("workflow_id", "")
    if not workflow_id:
        raise ValueError("workflow_id is required")
    run_id = merged.get("run_id", "")
    if not run_id:
        raise ValueError("run_id is required")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{COPY_AI_BASE}/workflow/{workflow_id}/run/{run_id}",
            headers={"x-copy-ai-api-key": api_key},
        )
        r.raise_for_status()
        result = r.json()

    log.info("copy_ai.get_run_result", workflow_id=workflow_id, run_id=run_id)
    return result
