"""ExecuteWorkflow integration — trigger another workflow via internal API."""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


@register_node("execute_workflow.run")
async def execute_workflow_run(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Trigger another workflow by ID and return its execution result."""
    cred = await get_credential_data(credential_id, db)

    api_url = cred.get("api_url", "").rstrip("/")
    api_key = cred.get("api_key", "")

    workflow_id = config.get("workflow_id") or input_data.get("workflow_id")
    input_payload = config.get("input_data") or input_data.get("input_data") or {}

    if not workflow_id:
        raise ValueError("execute_workflow.run: 'workflow_id' is required")

    log.info("execute_workflow.run", workflow_id=workflow_id, api_url=api_url)

    url = f"{api_url}/api/workflows/{workflow_id}/execute"
    headers = {
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(url, json=input_payload, headers=headers)
        r.raise_for_status()
        data = r.json()

    log.info("execute_workflow.run completed", workflow_id=workflow_id, status=r.status_code)
    return {
        "workflow_id": workflow_id,
        "execution_id": data.get("execution_id"),
        "status": data.get("status"),
        "output": data.get("output"),
        "raw": data,
    }
