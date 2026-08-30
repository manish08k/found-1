"""Executions router — production version."""
import hashlib
import hmac as hmac_lib
import json as json_lib
import uuid
from datetime import datetime
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.auth import get_current_user
from core.plans import execution_history_cutoff
from storage.database import get_db, get_db_read
from storage.models import (
    Execution, ExecutionStatus, Workflow, User,
    WebhookEndpoint, WorkflowStatus,
)
from core.execution_engine import resume_execution

log = structlog.get_logger(__name__)
router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────

class ResumeRequest(BaseModel):
    node_id: str
    approved: bool
    comment: Optional[str] = None
    approved_by: Optional[str] = None


class ManualRunRequest(BaseModel):
    trigger_data: Optional[dict] = None


# ─── List ─────────────────────────────────────────────────────────────────────

@router.get("")
async def list_executions(
    workflow_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_read),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(Execution)
        .join(Workflow, Execution.workflow_id == Workflow.id)
        .where(Workflow.owner_id == user.id)
        .order_by(Execution.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    if workflow_id:
        stmt = stmt.where(Execution.workflow_id == workflow_id)
    if status:
        stmt = stmt.where(Execution.status == status)

    cutoff = await execution_history_cutoff(user, db)
    if cutoff:
        stmt = stmt.where(Execution.created_at >= cutoff)

    result = await db.execute(stmt)
    return {"executions": [_serialize(e) for e in result.scalars().all()]}


# ─── Get ──────────────────────────────────────────────────────────────────────

@router.get("/{execution_id}")
async def get_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _serialize(await _load(execution_id, user.id, db), full=True)


# ─── Manual run ───────────────────────────────────────────────────────────────

@router.post("/workflows/{workflow_id}/run")
async def manual_run(
    workflow_id: str,
    body: ManualRunRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    wf = await _load_workflow(workflow_id, user.id, db)
    execution = Execution(
        id=str(uuid.uuid4()),
        workflow_id=workflow_id,
        status=ExecutionStatus.queued,
        trigger_type="manual",
        trigger_data=body.trigger_data or {},
    )
    db.add(execution)
    await db.flush()

    from workers.tasks import run_workflow_task
    run_workflow_task.delay(
        execution_id=execution.id,
        workflow_definition=wf.definition,
        trigger_data=body.trigger_data or {},
    )
    await db.commit()
    return {"execution_id": execution.id, "status": execution.status}


# ─── Resume (human approval) ──────────────────────────────────────────────────

@router.post("/{execution_id}/resume")
async def resume(
    execution_id: str,
    body: ResumeRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    execution = await _load(execution_id, user.id, db)
    if execution.status not in ("waiting", "running"):
        raise HTTPException(409, f"Execution is {execution.status}, cannot resume")

    await resume_execution(
        execution_id=execution_id,
        node_id=body.node_id,
        approval={
            "approved": body.approved,
            "comment": body.comment or "",
            "approved_by": body.approved_by or user.email,
        },
    )
    return {"ok": True, "execution_id": execution_id, "node_id": body.node_id}


# ─── Cancel ───────────────────────────────────────────────────────────────────

@router.post("/{execution_id}/cancel")
async def cancel_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    execution = await _load(execution_id, user.id, db)
    if execution.status not in ("queued", "running", "waiting"):
        raise HTTPException(409, f"Cannot cancel a {execution.status} execution")

    await db.execute(
        update(Execution)
        .where(Execution.id == execution_id)
        .values(status=ExecutionStatus.cancelled, finished_at=datetime.utcnow())
    )
    await db.commit()
    return {"ok": True, "execution_id": execution_id}


# ─── Retry ────────────────────────────────────────────────────────────────────

@router.post("/{execution_id}/retry")
async def retry_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    old = await _load(execution_id, user.id, db)
    if old.status not in ("failed", "cancelled"):
        raise HTTPException(409, "Only failed or cancelled executions can be retried")

    wf = await _load_workflow(old.workflow_id, user.id, db)
    new_exec = Execution(
        id=str(uuid.uuid4()),
        workflow_id=old.workflow_id,
        status=ExecutionStatus.queued,
        trigger_type=old.trigger_type,
        trigger_data=old.trigger_data or {},
    )
    db.add(new_exec)
    await db.flush()

    from workers.tasks import run_workflow_task
    run_workflow_task.delay(
        execution_id=new_exec.id,
        workflow_definition=wf.definition,
        trigger_data=old.trigger_data or {},
    )
    await db.commit()
    return {"execution_id": new_exec.id, "status": new_exec.status}


# ─── Debug ───────────────────────────────────────────────────────────────────

@router.get("/{execution_id}/debug")
async def debug_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Full debug info per node: input, output, timing, errors."""
    execution = await _load(execution_id, user.id, db)
    node_results = execution.node_results or {}

    debug_nodes = []
    for node_id, result in node_results.items():
        if not isinstance(result, dict):
            debug_nodes.append({"node_id": node_id, "raw": result})
            continue

        debug_nodes.append({
            "node_id": node_id,
            "status": result.get("status", "unknown"),
            "input_data": result.get("input_data"),
            "output_data": result.get("output") or result.get("output_data"),
            "error": result.get("error"),
            "started_at": result.get("started_at"),
            "finished_at": result.get("finished_at"),
            "duration_ms": result.get("duration_ms"),
            "retries": result.get("retries", 0),
        })

    return {
        "execution_id": execution.id,
        "workflow_id": execution.workflow_id,
        "status": execution.status,
        "trigger_data": execution.trigger_data,
        "error": execution.error,
        "started_at": execution.started_at.isoformat() if execution.started_at else None,
        "finished_at": execution.finished_at.isoformat() if execution.finished_at else None,
        "nodes": debug_nodes,
    }


@router.post("/{execution_id}/retry-node/{node_id}")
async def retry_single_node(
    execution_id: str,
    node_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Retry a single failed node within an execution."""
    execution = await _load(execution_id, user.id, db)
    node_results = dict(execution.node_results or {})

    node_result = node_results.get(node_id)
    if not node_result or not isinstance(node_result, dict):
        raise HTTPException(404, f"Node {node_id} not found in execution results")

    if node_result.get("status") != "error":
        raise HTTPException(409, f"Node {node_id} is not in error state (status={node_result.get('status')})")

    # Clear the failed node result so it gets re-executed
    node_results[node_id] = {"status": "pending_retry"}
    execution.node_results = node_results
    execution.status = ExecutionStatus.running
    execution.error = None
    await db.commit()

    wf = await _load_workflow(execution.workflow_id, user.id, db)

    from workers.tasks import run_workflow_task
    run_workflow_task.apply_async(
        args=[execution.id, wf.definition, execution.trigger_data or {}],
        queue="workflows",
    )
    return {"ok": True, "execution_id": execution_id, "node_id": node_id, "status": "retrying"}


@router.post("/{execution_id}/replay")
async def replay_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Replay entire execution from scratch with same trigger data."""
    old = await _load(execution_id, user.id, db)
    wf = await _load_workflow(old.workflow_id, user.id, db)

    new_exec = Execution(
        id=str(uuid.uuid4()),
        workflow_id=old.workflow_id,
        status=ExecutionStatus.queued,
        trigger_type="replay",
        trigger_data=old.trigger_data or {},
    )
    db.add(new_exec)
    await db.flush()

    from workers.tasks import run_workflow_task
    run_workflow_task.delay(
        execution_id=new_exec.id,
        workflow_definition=wf.definition,
        trigger_data=old.trigger_data or {},
    )
    await db.commit()
    return {
        "execution_id": new_exec.id,
        "replayed_from": execution_id,
        "status": "queued",
    }


@router.post("/{execution_id}/replay-from/{node_id}")
async def replay_from_node(
    execution_id: str,
    node_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Replay from a specific node, keeping earlier results intact."""
    execution = await _load(execution_id, user.id, db)
    wf = await _load_workflow(execution.workflow_id, user.id, db)

    # Create new execution with partial results
    old_results = dict(execution.node_results or {})

    # Keep results for nodes that come before node_id in topological order
    from core.execution_engine import topological_sort

    nodes = wf.definition.get("nodes", [])
    edges = wf.definition.get("edges", [])

    try:
        levels = topological_sort(nodes, edges)
    except ValueError:
        raise HTTPException(400, "Workflow graph has a cycle")

    # Find which nodes come before node_id
    keep_nodes = set()
    found = False
    for level in levels:
        if node_id in level:
            found = True
            break
        for nid in level:
            keep_nodes.add(nid)

    if not found:
        raise HTTPException(404, f"Node {node_id} not found in workflow")

    # Only keep results for nodes before the target
    partial_results = {nid: old_results[nid] for nid in keep_nodes if nid in old_results}

    new_exec = Execution(
        id=str(uuid.uuid4()),
        workflow_id=execution.workflow_id,
        status=ExecutionStatus.queued,
        trigger_type="replay_from",
        trigger_data=execution.trigger_data or {},
        node_results=partial_results,
    )
    db.add(new_exec)
    await db.flush()

    from workers.tasks import run_workflow_task
    run_workflow_task.delay(
        execution_id=new_exec.id,
        workflow_definition=wf.definition,
        trigger_data=execution.trigger_data or {},
    )
    await db.commit()
    return {
        "execution_id": new_exec.id,
        "replayed_from": execution_id,
        "replay_start_node": node_id,
        "kept_nodes": list(keep_nodes),
        "status": "queued",
    }


# ─── Webhook receive ──────────────────────────────────────────────────────────

async def receive_webhook(path_token: str, request, db: AsyncSession) -> dict:
    result = await db.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.path_token == path_token,
            WebhookEndpoint.is_active == True,
        )
    )
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(404, "Webhook not found")

    body = await request.body()
    headers = dict(request.headers)

    if endpoint.secret:
        sig = headers.get("x-autoflow-signature") or headers.get("x-hub-signature-256", "")
        expected = "sha256=" + hmac_lib.new(
            endpoint.secret.encode(), body, hashlib.sha256
        ).hexdigest()
        if not hmac_lib.compare_digest(expected, sig):
            raise HTTPException(401, "Invalid webhook signature")

    try:
        payload = json_lib.loads(body)
    except Exception:
        payload = {"raw": body.decode(errors="replace")}

    wf_result = await db.execute(
        select(Workflow).where(
            Workflow.id == endpoint.workflow_id,
            Workflow.status == WorkflowStatus.active,
        )
    )
    workflow = wf_result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(404, "Workflow not found or inactive")

    execution = Execution(
        id=str(uuid.uuid4()),
        workflow_id=workflow.id,
        status=ExecutionStatus.queued,
        trigger_type="webhook",
        trigger_data={
            "headers": headers,
            "payload": payload,
            "path_token": path_token,
            "query_params": dict(request.query_params),
        },
    )
    db.add(execution)
    await db.flush()

    from workers.tasks import run_workflow_task
    run_workflow_task.delay(
        execution_id=execution.id,
        workflow_definition=workflow.definition,
        trigger_data=execution.trigger_data,
    )
    await db.commit()

    log.info("webhook_received", path_token=path_token, execution_id=execution.id)
    return {"ok": True, "execution_id": execution.id}


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _load(execution_id: str, owner_id: str, db: AsyncSession) -> Execution:
    result = await db.execute(
        select(Execution)
        .join(Workflow, Execution.workflow_id == Workflow.id)
        .where(Execution.id == execution_id, Workflow.owner_id == owner_id)
    )
    e = result.scalar_one_or_none()
    if not e:
        raise HTTPException(404, "Execution not found")
    return e


async def _load_workflow(workflow_id: str, owner_id: str, db: AsyncSession) -> Workflow:
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.owner_id == owner_id)
    )
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(404, "Workflow not found")
    return wf


def _serialize(e: Execution, full: bool = False) -> dict:
    d = {
        "id": e.id,
        "workflow_id": e.workflow_id,
        "status": e.status,
        "trigger_type": e.trigger_type,
        "error": e.error,
        "started_at": e.started_at.isoformat() if e.started_at else None,
        "finished_at": e.finished_at.isoformat() if e.finished_at else None,
        "created_at": e.created_at.isoformat(),
        "duration_ms": (
            int((e.finished_at - e.started_at).total_seconds() * 1000)
            if e.started_at and e.finished_at else None
        ),
    }
    if full:
        d["node_results"] = e.node_results
        d["trigger_data"] = e.trigger_data
    return d