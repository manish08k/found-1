"""
Approvals — the human-in-the-loop API. A workflow's approval.wait node
(integrations/core/nodes.py) pauses execution and creates a pending
Approval row; these routes are how a human sees and decides it, and how
that decision resumes the SAME execution (not a fresh run — see
core/execution_engine.py's resume-from-waiting handling, which skips
every node that already completed before the pause).
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.auth import get_current_user
from storage.database import get_db
from storage.models import Approval, Execution, Workflow, User, ExecutionStatus

router = APIRouter(prefix="/api/approvals", tags=["Approvals"])


def _serialize(a: Approval) -> dict:
    return {
        "id": a.id, "execution_id": a.execution_id, "node_id": a.node_id, "status": a.status,
        "workflow_id": a.workflow_id, "assigned_to": a.assigned_to,
        "prompt": a.prompt, "payload": a.payload, "response_payload": a.response_payload,
        "reason": a.reason, "edited_data": a.edited_data,
        "decided_by": a.decided_by,
        "created_at": a.created_at.isoformat(), "expires_at": a.expires_at.isoformat() if a.expires_at else None,
        "decided_at": a.decided_at.isoformat() if a.decided_at else None,
    }


async def _owned_approval(approval_id: str, user: User, db: AsyncSession) -> Approval:
    result = await db.execute(
        select(Approval).join(Execution, Execution.id == Approval.execution_id)
        .join(Workflow, Workflow.id == Execution.workflow_id)
        .where(Approval.id == approval_id, Workflow.owner_id == user.id)
    )
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    return approval


@router.get("")
async def list_approvals(
    status: str = "pending",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Pending approvals across all of this user's workflows — the "needs your review" inbox."""
    stmt = (
        select(Approval).join(Execution, Execution.id == Approval.execution_id)
        .join(Workflow, Workflow.id == Execution.workflow_id)
        .where(Workflow.owner_id == user.id)
        .order_by(Approval.created_at.desc())
    )
    if status:
        stmt = stmt.where(Approval.status == status)
    result = await db.execute(stmt)
    return {"approvals": [_serialize(a) for a in result.scalars().all()]}


@router.get("/{approval_id}")
async def get_approval(approval_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return _serialize(await _owned_approval(approval_id, user, db))


class ApprovalDecision(BaseModel):
    decision: str  # "approve" | "reject" | "edit"
    response_payload: dict | None = None  # e.g. an edited version of the content being approved
    reason: str | None = None  # reason for the decision
    edited_data: dict | None = None  # modified data (for "edit" decisions)


@router.post("/{approval_id}/decide")
async def decide_approval(
    approval_id: str,
    body: ApprovalDecision,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if body.decision not in ("approve", "reject", "edit"):
        raise HTTPException(status_code=400, detail="decision must be 'approve', 'reject', or 'edit'")

    approval = await _owned_approval(approval_id, user, db)
    if approval.status != "pending":
        raise HTTPException(status_code=409, detail=f"This approval was already decided ({approval.status})")

    if body.decision == "edit":
        approval.status = "approved"
    else:
        approval.status = "approved" if body.decision == "approve" else "rejected"
    approval.response_payload = body.response_payload
    approval.decided_by = user.id
    approval.decided_at = datetime.utcnow()
    approval.reason = body.reason
    approval.edited_data = body.edited_data

    exec_result = await db.execute(select(Execution).where(Execution.id == approval.execution_id))
    execution = exec_result.scalar_one_or_none()
    if not execution:
        raise HTTPException(status_code=404, detail="The execution this approval belongs to no longer exists")

    if body.decision == "reject":
        # Rejecting stops the workflow here — mark it failed with a clear,
        # specific reason rather than leaving it stuck in `waiting` forever.
        execution.status = ExecutionStatus.failed
        execution.error = f"Rejected at approval.wait node '{approval.node_id}' by user {user.id}"
        await db.commit()
        return {"status": "rejected", "execution_status": execution.status.value}

    # Approved: mark this node's result as approved (so the resumed run's
    # "already completed" check treats it as done, not something to
    # re-pause on) and re-dispatch the SAME execution to resume from here.
    node_results = dict(execution.node_results or {})
    node_results[approval.node_id] = {
        "status": "success",
        "output": {"approved": True, "response_payload": body.response_payload, "decided_by": user.id},
    }
    execution.node_results = node_results
    await db.commit()

    wf_result = await db.execute(select(Workflow).where(Workflow.id == execution.workflow_id))
    workflow = wf_result.scalar_one()

    from workers.tasks import run_workflow_task
    run_workflow_task.apply_async(
        args=[execution.id, workflow.definition, execution.trigger_data or {}],
        queue="workflows",
    )
    return {"status": "approved", "execution_status": "resuming"}


@router.get("/history")
async def approval_history(
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Audit history of all approval decisions made by the user or across their workflows."""
    stmt = (
        select(Approval)
        .join(Execution, Execution.id == Approval.execution_id)
        .join(Workflow, Workflow.id == Execution.workflow_id)
        .where(
            Workflow.owner_id == user.id,
            Approval.status != "pending",
        )
        .order_by(Approval.decided_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    approvals = result.scalars().all()
    return {
        "history": [_serialize(a) for a in approvals],
        "page": page,
        "page_size": page_size,
    }
