"""Air Ops AI workflow automation — handler for air_ops integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.air.ai/v1"


@register_node("air_ops.run_workflow")
async def air_ops_run_workflow(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Execute a workflow.

    config/input_data:
      api_key — API key or token (required)
      workflow_id — (required)
      inputs — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    workflow_id = merged.get("workflow_id") or ""
    inputs = merged.get("inputs") or ""
    if not workflow_id or not inputs:
        raise ValueError("workflow_id, inputs required for air_ops.run_workflow")
    payload = {"inputs": inputs}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/workflows/{workflow_id}/run", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("air_ops.run_workflow")
    return {"data": data}

@register_node("air_ops.list_workflows")
async def air_ops_list_workflows(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all workflows.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/workflows", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("air_ops.list_workflows")
    return {"data": data}

@register_node("air_ops.get_run_status")
async def air_ops_get_run_status(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get run status.

    config/input_data:
      api_key — API key or token (required)
      run_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    run_id = merged.get("run_id") or ""
    if not run_id:
        raise ValueError("run_id required for air_ops.get_run_status")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/runs/{run_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("air_ops.get_run_status")
    return {"data": data}
