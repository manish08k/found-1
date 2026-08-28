"""Dead Letter Queue — list, replay, abandon."""
from fastapi import APIRouter, Depends, HTTPException, Query

from api.middleware.rbac import require_permission
from core.dlq import abandon_dlq_item, list_dlq, replay_dlq_item
from storage.database import get_db, get_db_read
from sqlalchemy.ext.asyncio import AsyncSession
from storage.models import User

router = APIRouter()


@router.get("")
async def get_dlq(
    status: str | None = Query(default="pending"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_read),
    user: User = Depends(require_permission("dlq:replay")),
):
    items = await list_dlq(db, user.org_id, status, page, limit)
    return [
        {
            "id": i.id, "workflow_id": i.workflow_id, "execution_id": i.execution_id,
            "task_name": i.task_name, "error": i.error, "retry_count": i.retry_count,
            "status": i.status, "created_at": i.created_at.isoformat(),
        }
        for i in items
    ]


@router.post("/{dlq_id}/replay")
async def replay(
    dlq_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("dlq:replay")),
):
    try:
        await replay_dlq_item(db, dlq_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    return {"message": "Job queued for replay"}


@router.post("/{dlq_id}/abandon")
async def abandon(
    dlq_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("dlq:replay")),
):
    try:
        await abandon_dlq_item(db, dlq_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    return {"message": "Item abandoned"}
