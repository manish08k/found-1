"""Captain Data automated data extraction — handler for captain_data integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.captaindata.co/v3"


@register_node("captain_data.list_workflows")
async def captain_data_list_workflows(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List workflows.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/workflows", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("captain_data.list_workflows")
    return {"data": data}

@register_node("captain_data.launch_workflow")
async def captain_data_launch_workflow(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Launch a workflow.

    config/input_data:
      api_key — API key or token (required)
      workflow_id — (required)
      inputs — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    workflow_id = merged.get("workflow_id") or ""
    inputs = merged.get("inputs") or ""
    if not workflow_id or not inputs:
        raise ValueError("workflow_id, inputs required for captain_data.launch_workflow")
    payload = {"inputs": inputs}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/workflows/{workflow_id}/jobs", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("captain_data.launch_workflow")
    return {"data": data}

@register_node("captain_data.get_job")
async def captain_data_get_job(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get job results.

    config/input_data:
      api_key — API key or token (required)
      job_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    job_id = merged.get("job_id") or ""
    if not job_id:
        raise ValueError("job_id required for captain_data.get_job")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/jobs/{job_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("captain_data.get_job")
    return {"data": data}
