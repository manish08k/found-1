"""
N8n self-management API integration.

Provides workflow listing, retrieval, activation, and execution listing via
the N8n REST API v1.

Credential fields:
  - base_url : N8n instance base URL, e.g. https://n8n.example.com
  - api_key  : N8n API key (Settings > API > Create API key)

Auth: Bearer token in Authorization header.
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    base_url = creds.get("base_url", "").rstrip("/")
    api_key = creds.get("api_key")
    if not base_url:
        raise ValueError("N8n credential missing 'base_url'")
    if not api_key:
        raise ValueError("N8n credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=f"{base_url}/api/v1/",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"N8n API error {r.status_code}: {detail}")


@register_node("n8n_node.list_workflows")
async def n8n_list_workflows(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all workflows in the N8n instance."""
    active_only = bool(config.get("active") or input_data.get("active", False))
    limit = int(config.get("limit") or input_data.get("limit", 25))
    cursor = config.get("cursor") or input_data.get("cursor")

    params: dict = {"limit": limit}
    if active_only:
        params["active"] = "true"
    if cursor:
        params["cursor"] = cursor

    log.info("n8n_node.list_workflows", limit=limit, active_only=active_only)
    async with await _client(credential_id, db) as client:
        r = await client.get("workflows", params=params)
        _raise_for_status(r)
        data = r.json()

    return {
        "workflows": data.get("data", []),
        "next_cursor": data.get("nextCursor"),
        "count": len(data.get("data", [])),
    }


@register_node("n8n_node.get_workflow")
async def n8n_get_workflow(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve a specific workflow by ID."""
    workflow_id = config.get("workflow_id") or input_data.get("workflow_id")
    if not workflow_id:
        raise ValueError("n8n_node.get_workflow requires 'workflow_id'")

    log.info("n8n_node.get_workflow", workflow_id=workflow_id)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"workflows/{workflow_id}")
        _raise_for_status(r)
        data = r.json()

    return {"workflow": data, "workflow_id": data.get("id"), "active": data.get("active", False)}


@register_node("n8n_node.activate_workflow")
async def n8n_activate_workflow(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Activate or deactivate a workflow."""
    workflow_id = config.get("workflow_id") or input_data.get("workflow_id")
    if not workflow_id:
        raise ValueError("n8n_node.activate_workflow requires 'workflow_id'")

    activate = bool(config.get("activate") if config.get("activate") is not None else input_data.get("activate", True))

    log.info("n8n_node.activate_workflow", workflow_id=workflow_id, activate=activate)
    async with await _client(credential_id, db) as client:
        if activate:
            r = await client.post(f"workflows/{workflow_id}/activate")
        else:
            r = await client.post(f"workflows/{workflow_id}/deactivate")
        _raise_for_status(r)
        data = r.json()

    return {
        "workflow": data,
        "workflow_id": data.get("id", workflow_id),
        "active": data.get("active", activate),
    }


@register_node("n8n_node.list_executions")
async def n8n_list_executions(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List workflow executions, optionally filtered by workflow and status."""
    workflow_id = config.get("workflow_id") or input_data.get("workflow_id")
    status = config.get("status") or input_data.get("status")
    limit = int(config.get("limit") or input_data.get("limit", 20))
    cursor = config.get("cursor") or input_data.get("cursor")
    include_data = bool(config.get("include_data") or input_data.get("include_data", False))

    params: dict = {"limit": limit}
    if workflow_id:
        params["workflowId"] = str(workflow_id)
    if status:
        params["status"] = status
    if cursor:
        params["cursor"] = cursor
    if include_data:
        params["includeData"] = "true"

    log.info("n8n_node.list_executions", workflow_id=workflow_id, status=status, limit=limit)
    async with await _client(credential_id, db) as client:
        r = await client.get("executions", params=params)
        _raise_for_status(r)
        data = r.json()

    return {
        "executions": data.get("data", []),
        "next_cursor": data.get("nextCursor"),
        "count": len(data.get("data", [])),
    }
