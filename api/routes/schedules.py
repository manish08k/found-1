"""Schedules router."""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from storage.database import get_db
from storage.models import Schedule, Workflow
from api.middleware.auth import get_current_user
from schedules.manager import add_schedule, remove_schedule

router = APIRouter()


class ScheduleCreate(BaseModel):
    workflow_id: str
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    timezone: str = "UTC"


@router.get("")
async def list_schedules(
    workflow_id: str = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    q = select(Schedule).join(Workflow).where(Workflow.owner_id == user.id)
    if workflow_id:
        q = q.where(Schedule.workflow_id == workflow_id)
    result = await db.execute(q)
    schedules = result.scalars().all()
    return {"schedules": [_serialize(s) for s in schedules]}


@router.post("", status_code=201)
async def create_schedule(
    body: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    if not body.cron_expression and not body.interval_seconds:
        raise HTTPException(status_code=400, detail="Provide cron_expression or interval_seconds")

    wf_result = await db.execute(
        select(Workflow).where(Workflow.id == body.workflow_id, Workflow.owner_id == user.id)
    )
    if not wf_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Validate cron
    if body.cron_expression:
        from croniter import croniter
        if not croniter.is_valid(body.cron_expression):
            raise HTTPException(status_code=400, detail="Invalid cron expression")

    schedule = Schedule(
        id=str(uuid.uuid4()),
        workflow_id=body.workflow_id,
        cron_expression=body.cron_expression,
        interval_seconds=body.interval_seconds,
        timezone=body.timezone,
    )
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    await add_schedule(schedule)
    return _serialize(schedule)


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(
        select(Schedule).join(Workflow).where(Schedule.id == schedule_id, Workflow.owner_id == user.id)
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await remove_schedule(schedule_id)
    await db.delete(schedule)
    await db.commit()


@router.patch("/{schedule_id}/toggle")
async def toggle_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(
        select(Schedule).join(Workflow).where(Schedule.id == schedule_id, Workflow.owner_id == user.id)
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    schedule.is_active = not schedule.is_active
    if schedule.is_active:
        await add_schedule(schedule)
    else:
        await remove_schedule(schedule_id)
    await db.commit()
    return {"is_active": schedule.is_active}


def _serialize(s: Schedule) -> dict:
    return {
        "id": s.id,
        "workflow_id": s.workflow_id,
        "cron_expression": s.cron_expression,
        "interval_seconds": s.interval_seconds,
        "timezone": s.timezone,
        "is_active": s.is_active,
        "next_run_at": s.next_run_at.isoformat() if s.next_run_at else None,
        "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
    }
