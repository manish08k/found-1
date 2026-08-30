"""
AI Cost and Model Routing — execution cost tracking and budget management.
"""
from datetime import datetime, timedelta
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.auth import get_current_user
from storage.database import get_db
from storage.models import ExecutionCost, Execution, Workflow, User

log = structlog.get_logger(__name__)

router = APIRouter()


class BudgetRequest(BaseModel):
    workflow_id: Optional[str] = None
    monthly_budget_usd: float
    alert_threshold_pct: float = 80.0  # alert at 80% of budget


@router.get("/executions/{execution_id}")
async def get_execution_costs(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get per-execution cost breakdown."""
    # Verify ownership
    exec_result = await db.execute(
        select(Execution)
        .join(Workflow, Workflow.id == Execution.workflow_id)
        .where(Execution.id == execution_id, Workflow.owner_id == user.id)
    )
    if not exec_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Execution not found")

    from core.cost_tracker import get_execution_cost_summary
    summary = await get_execution_cost_summary(execution_id, db)
    return summary


@router.get("/workflows/{workflow_id}")
async def get_workflow_costs(
    workflow_id: str,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get workflow aggregate costs over time."""
    wf_result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.owner_id == user.id,
        )
    )
    if not wf_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Workflow not found")

    from core.cost_tracker import get_workflow_cost_analytics

    start_date = datetime.utcnow() - timedelta(days=days)
    analytics = await get_workflow_cost_analytics(
        workflow_id, start_date=start_date, db=db
    )
    return analytics


@router.get("/summary")
async def get_cost_summary(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Workspace total costs with model breakdown."""
    start_date = datetime.utcnow() - timedelta(days=days)

    # Get all execution IDs for user's workflows
    exec_result = await db.execute(
        select(Execution.id)
        .join(Workflow, Workflow.id == Execution.workflow_id)
        .where(
            Workflow.owner_id == user.id,
            Execution.created_at >= start_date,
        )
    )
    execution_ids = [r[0] for r in exec_result.all()]

    if not execution_ids:
        return {
            "total_cost_usd": 0.0,
            "total_tokens": 0,
            "execution_count": len(execution_ids),
            "by_model": {},
            "by_workflow": {},
            "period_days": days,
        }

    # Aggregate by model
    model_result = await db.execute(
        select(
            ExecutionCost.model,
            ExecutionCost.provider,
            func.sum(ExecutionCost.input_tokens).label("total_input"),
            func.sum(ExecutionCost.output_tokens).label("total_output"),
            func.sum(ExecutionCost.total_tokens).label("total_tokens"),
            func.sum(ExecutionCost.estimated_cost_usd).label("total_cost"),
            func.count(ExecutionCost.id).label("call_count"),
        )
        .where(ExecutionCost.execution_id.in_(execution_ids))
        .group_by(ExecutionCost.model, ExecutionCost.provider)
    )
    model_rows = model_result.all()

    by_model = {}
    total_cost = 0
    total_tokens = 0
    for row in model_rows:
        key = f"{row.provider}/{row.model}" if row.provider else (row.model or "unknown")
        cost = row.total_cost or 0
        by_model[key] = {
            "input_tokens": row.total_input or 0,
            "output_tokens": row.total_output or 0,
            "cost_usd": round(cost / 1_000_000, 6),
            "call_count": row.call_count,
        }
        total_cost += cost
        total_tokens += (row.total_tokens or 0)

    # Aggregate by workflow
    wf_cost_result = await db.execute(
        select(
            Execution.workflow_id,
            func.sum(ExecutionCost.estimated_cost_usd).label("total_cost"),
            func.count(ExecutionCost.id).label("call_count"),
        )
        .join(Execution, Execution.id == ExecutionCost.execution_id)
        .where(ExecutionCost.execution_id.in_(execution_ids))
        .group_by(Execution.workflow_id)
    )
    wf_rows = wf_cost_result.all()
    by_workflow = {
        r.workflow_id: {"cost_usd": round((r.total_cost or 0) / 1_000_000, 6), "call_count": r.call_count}
        for r in wf_rows
    }

    return {
        "total_cost_usd": round(total_cost / 1_000_000, 6),
        "total_tokens": total_tokens,
        "execution_count": len(execution_ids),
        "by_model": by_model,
        "by_workflow": by_workflow,
        "period_days": days,
    }


@router.post("/budgets")
async def set_budget(
    body: BudgetRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Set a budget limit and check current spend against it."""
    start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Get current month's spend
    exec_stmt = select(Execution.id).join(
        Workflow, Workflow.id == Execution.workflow_id
    ).where(
        Workflow.owner_id == user.id,
        Execution.created_at >= start_of_month,
    )
    if body.workflow_id:
        exec_stmt = exec_stmt.where(Execution.workflow_id == body.workflow_id)

    exec_result = await db.execute(exec_stmt)
    execution_ids = [r[0] for r in exec_result.all()]

    current_spend = 0.0
    if execution_ids:
        cost_result = await db.execute(
            select(func.sum(ExecutionCost.estimated_cost_usd))
            .where(ExecutionCost.execution_id.in_(execution_ids))
        )
        total_microdollars = cost_result.scalar_one() or 0
        current_spend = total_microdollars / 1_000_000

    budget = body.monthly_budget_usd
    spend_pct = (current_spend / budget * 100) if budget > 0 else 0

    alert = spend_pct >= body.alert_threshold_pct
    over_budget = current_spend >= budget

    return {
        "monthly_budget_usd": budget,
        "current_spend_usd": round(current_spend, 6),
        "spend_percentage": round(spend_pct, 1),
        "alert": alert,
        "over_budget": over_budget,
        "workflow_id": body.workflow_id,
        "period_start": start_of_month.isoformat(),
    }
