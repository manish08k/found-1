"""
MCP SERVER — the other half of the MCP story (integrations/mcp_/handler.py
is the client). Exposes a user's active workflows as MCP tools: any
MCP-compliant client (Claude Desktop, another agent framework) can
connect to /api/mcp/{api_key}, list this user's workflows as tools, and
call one to trigger a real execution.

Auth: a per-user MCP API key (separate from the JWT bearer tokens used
everywhere else) embedded in the connection URL — this matches how MCP
clients actually connect (a static URL in their config file, not an
interactive login), the same reasoning Slack/GitHub webhook URLs in this
project already use a URL-embedded secret rather than a header.
"""
import itertools
import secrets

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.auth import get_current_user
from core.config import settings
from storage.database import get_db, db_context
from storage.models import User, Workflow, WorkflowStatus, Execution, ExecutionStatus

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/mcp", tags=["MCP Server"])

MCP_PROTOCOL_VERSION = "2025-06-18"
_id_counter = itertools.count(1)


def generate_mcp_api_key() -> str:
    return f"af_mcp_{secrets.token_urlsafe(32)}"


def _rpc_response(req_id, result=None, error=None):
    body = {"jsonrpc": "2.0", "id": req_id}
    if error:
        body["error"] = error
    else:
        body["result"] = result
    return JSONResponse(body)


def _workflow_to_tool(wf: Workflow) -> dict:
    """
    A workflow becomes an MCP tool named after its ID. Input schema is
    intentionally generic (any-shaped JSON object) — AutoFlow workflows
    don't currently declare a formal input schema, so this accepts
    trigger_data as free-form JSON, exactly like a webhook trigger would.
    """
    return {
        "name": f"workflow_{wf.id}",
        "description": wf.description or f"Runs the AutoFlow workflow '{wf.name}'",
        "inputSchema": {
            "type": "object",
            "properties": {"input": {"type": "object", "description": "Arbitrary JSON passed to the workflow as trigger data"}},
        },
    }


@router.post("/generate-key")
async def generate_key(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Rotates (or creates for the first time) this user's MCP server key.
    The full URL to give an MCP client is {APP_BASE_URL}/api/mcp/{key} —
    returned once here; if lost, generate a new one (this invalidates
    the old one immediately, same as any other secret rotation).
    """
    key = generate_mcp_api_key()
    user.mcp_api_key = key
    await db.commit()
    base_url = settings.APP_BASE_URL or "http://localhost:8000"
    return {"mcp_api_key": key, "connection_url": f"{base_url}/api/mcp/{key}"}


@router.delete("/key")
async def revoke_key(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    user.mcp_api_key = None
    await db.commit()
    return {"revoked": True}


@router.get("/status")
async def mcp_status(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    wf_result = await db.execute(
        select(Workflow).where(Workflow.owner_id == user.id, Workflow.status == WorkflowStatus.active)
    )
    tool_count = len(wf_result.scalars().all())
    base_url = settings.APP_BASE_URL or "http://localhost:8000"
    return {
        "enabled": user.mcp_api_key is not None,
        "connection_url": f"{base_url}/api/mcp/{user.mcp_api_key}" if user.mcp_api_key else None,
        "exposed_tool_count": tool_count,
    }


@router.post("/{api_key}")
async def mcp_server_rpc(api_key: str, request: Request):
    body = await request.json()
    method = body.get("method")
    req_id = body.get("id")
    params = body.get("params", {})

    async with db_context() as db:
        result = await db.execute(select(User).where(User.mcp_api_key == api_key, User.is_active == True))  # noqa: E712
        user = result.scalar_one_or_none()
        if not user:
            return _rpc_response(req_id, error={"code": -32001, "message": "Invalid or revoked MCP API key"})

        if method == "initialize":
            return _rpc_response(req_id, {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "autoflow", "version": "1.0"},
            })

        if method == "tools/list":
            wf_result = await db.execute(
                select(Workflow).where(Workflow.owner_id == user.id, Workflow.status == WorkflowStatus.active)
            )
            tools = [_workflow_to_tool(w) for w in wf_result.scalars().all()]
            return _rpc_response(req_id, {"tools": tools})

        if method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            if not tool_name.startswith("workflow_"):
                return _rpc_response(req_id, error={"code": -32602, "message": f"Unknown tool: {tool_name}"})
            workflow_id = tool_name[len("workflow_"):]

            wf_result = await db.execute(
                select(Workflow).where(Workflow.id == workflow_id, Workflow.owner_id == user.id, Workflow.status == WorkflowStatus.active)
            )
            workflow = wf_result.scalar_one_or_none()
            if not workflow:
                return _rpc_response(req_id, error={"code": -32602, "message": f"No active workflow matching tool: {tool_name}"})

            from core.plans import check_execution_limit
            try:
                await check_execution_limit(workflow.org_id, db)
            except Exception as e:
                return _rpc_response(req_id, error={"code": -32000, "message": str(getattr(e, "detail", e))})

            trigger_data = arguments.get("input", arguments)
            execution = Execution(workflow_id=workflow.id, status=ExecutionStatus.queued, trigger_type="mcp", trigger_data=trigger_data)
            db.add(execution)
            await db.commit()

            from workers.tasks import run_workflow_task
            run_workflow_task.apply_async(args=[execution.id, workflow.definition, trigger_data], queue="workflows")

            return _rpc_response(req_id, {
                "content": [{"type": "text", "text": f"Workflow '{workflow.name}' triggered. Execution ID: {execution.id}. Check /api/executions/{execution.id} for status."}],
                "isError": False,
            })

        return _rpc_response(req_id, error={"code": -32601, "message": f"Unknown method: {method}"})
