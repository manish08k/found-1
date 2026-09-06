"""
Manus AI agent platform integration.

Credential fields:
  - api_key: Manus API key
  - base_url: API base URL (default: https://api.manus.ai/v1)

Auth: Bearer token via Authorization header
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

DEFAULT_BASE_URL = "https://api.manus.ai/v1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Manus credential missing 'api_key'")
    base_url = creds.get("base_url", DEFAULT_BASE_URL).rstrip("/")
    return httpx.AsyncClient(
        base_url=base_url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=120.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Manus API error {r.status_code}: {detail}")
    try:
        return r.json()
    except Exception:
        return {"status": "ok"}


@register_node("manus.run_task")
async def manus_run_task(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /tasks — submit a task to the Manus AI agent."""
    task = config.get("task") or input_data.get("task")
    if not task:
        raise ValueError("manus.run_task requires 'task'")
    body: dict = {"task": task}
    context = config.get("context") or input_data.get("context")
    if context:
        body["context"] = context
    model = config.get("model") or input_data.get("model")
    if model:
        body["model"] = model
    async with await _client(credential_id, db) as client:
        r = await client.post("/tasks", json=body)
    return _check(r)


@register_node("manus.get_task_result")
async def manus_get_task_result(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /tasks/{task_id} — retrieve the result of a submitted task."""
    task_id = config.get("task_id") or input_data.get("task_id")
    if not task_id:
        raise ValueError("manus.get_task_result requires 'task_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/tasks/{task_id}")
    return _check(r)


@register_node("manus.list_tasks")
async def manus_list_tasks(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /tasks — list all tasks."""
    params = {}
    status = config.get("status") or input_data.get("status")
    if status:
        params["status"] = status
    limit = config.get("limit") or input_data.get("limit")
    if limit:
        params["limit"] = int(limit)
    async with await _client(credential_id, db) as client:
        r = await client.get("/tasks", params=params)
    return _check(r)


@register_node("manus.cancel_task")
async def manus_cancel_task(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /tasks/{task_id}/cancel — cancel a running task."""
    task_id = config.get("task_id") or input_data.get("task_id")
    if not task_id:
        raise ValueError("manus.cancel_task requires 'task_id'")
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/tasks/{task_id}/cancel")
    return _check(r)
