"""Dead Letter Queue — captures executions that exhausted Celery retries,
and supports manual replay/abandon."""
import traceback
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storage.database import db_context
from storage.models import DeadLetterItem, DLQStatus, Execution


async def push_to_dlq(
    execution_id: str | None,
    workflow_id: str | None,
    org_id: str | None,
    task_name: str,
    payload: dict,
    error: Exception,
) -> None:
    async with db_context() as db:
        item = DeadLetterItem(
            org_id=org_id,
            workflow_id=workflow_id,
            execution_id=execution_id,
            task_name=task_name,
            payload=payload,
            error=str(error),
            error_stack="".join(traceback.format_exception(type(error), error, error.__traceback__)),
            status=DLQStatus.pending,
        )
        db.add(item)


async def list_dlq(db: AsyncSession, org_id: str, status: str | None = "pending", page: int = 1, limit: int = 20):
    query = select(DeadLetterItem).where(DeadLetterItem.org_id == org_id)
    if status:
        query = query.where(DeadLetterItem.status == status)
    query = query.order_by(DeadLetterItem.created_at.desc()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def replay_dlq_item(db: AsyncSession, dlq_id: str) -> DeadLetterItem:
    result = await db.execute(select(DeadLetterItem).where(DeadLetterItem.id == dlq_id))
    item = result.scalar_one_or_none()
    if not item:
        raise ValueError("DLQ item not found")
    if item.status != DLQStatus.pending:
        raise ValueError(f"Cannot replay item in '{item.status.value}' status")

    item.status = DLQStatus.replaying

    from workers.tasks import run_workflow_task
    run_workflow_task.apply_async(
        args=[item.execution_id, item.payload.get("workflow_definition", {}), item.payload.get("trigger_data", {})],
        queue="workflows",
    )

    item.status = DLQStatus.resolved
    item.retry_count += 1
    return item


async def abandon_dlq_item(db: AsyncSession, dlq_id: str) -> DeadLetterItem:
    result = await db.execute(select(DeadLetterItem).where(DeadLetterItem.id == dlq_id))
    item = result.scalar_one_or_none()
    if not item:
        raise ValueError("DLQ item not found")
    item.status = DLQStatus.abandoned
    return item
