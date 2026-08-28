"""
Schedule Manager.

Loads all active schedules from DB at startup.
Supports cron expressions and interval-based schedules.
Persists next_run_at / last_run_at.
"""
import uuid
from datetime import datetime

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from storage.database import db_context
from storage.models import Execution, ExecutionStatus, Schedule, Workflow, WorkflowStatus

log = structlog.get_logger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")


async def load_schedules() -> None:
    """Load all active schedules from DB and register them with APScheduler."""
    async with db_context() as db:
        result = await db.execute(
            select(Schedule).where(Schedule.is_active == True)
        )
        schedules = result.scalars().all()

    for sched in schedules:
        _register_schedule(sched)

    log.info("schedules_loaded", count=len(schedules))


def _register_schedule(sched: Schedule) -> None:
    job_id = f"schedule_{sched.id}"

    if sched.cron_expression:
        trigger = CronTrigger.from_crontab(sched.cron_expression, timezone=sched.timezone)
    elif sched.interval_seconds:
        trigger = IntervalTrigger(seconds=sched.interval_seconds)
    else:
        log.warning("invalid_schedule", schedule_id=sched.id)
        return

    scheduler.add_job(
        _fire_schedule,
        trigger=trigger,
        id=job_id,
        replace_existing=True,
        args=[sched.id, sched.workflow_id],
    )


async def _fire_schedule(schedule_id: str, workflow_id: str) -> None:
    async with db_context() as db:
        wf_result = await db.execute(
            select(Workflow).where(
                Workflow.id == workflow_id,
                Workflow.status == WorkflowStatus.active,
            )
        )
        workflow = wf_result.scalar_one_or_none()
        if not workflow:
            return

        execution = Execution(
            id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            status=ExecutionStatus.queued,
            trigger_type="schedule",
            trigger_data={"schedule_id": schedule_id, "fired_at": datetime.utcnow().isoformat()},
        )
        db.add(execution)

        sched_result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
        sched = sched_result.scalar_one_or_none()
        if sched:
            sched.last_run_at = datetime.utcnow()

        await db.commit()

        from workers.tasks import run_workflow_task
        run_workflow_task.apply_async(
            args=[execution.id, workflow.definition, execution.trigger_data],
            queue="workflows",
        )
        log.info("schedule_fired", schedule_id=schedule_id, execution_id=execution.id)


async def add_schedule(schedule: Schedule) -> None:
    _register_schedule(schedule)


async def remove_schedule(schedule_id: str) -> None:
    job_id = f"schedule_{schedule_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)


async def start_scheduler() -> None:
    await load_schedules()
    scheduler.start()
    log.info("scheduler_started")


async def stop_scheduler() -> None:
    scheduler.shutdown(wait=False)
