"""
Feedback API — thumbs up/down on chat messages, suggestions, ratings.

Routes:
  POST   /api/feedback            — submit feedback on a message
  GET    /api/feedback            — list feedback
  GET    /api/feedback/stats      — aggregate stats (thumbs up/down ratio)
  DELETE /api/feedback/{id}       — delete feedback entry
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.auth import get_current_user
from storage.database import get_db
from storage.models import User, MessageFeedback

router = APIRouter()


class FeedbackCreate(BaseModel):
    message_id: str
    workflow_id: Optional[str] = None
    conversation_id: Optional[str] = None
    rating: int  # 1 = thumbs up, -1 = thumbs down
    content: Optional[str] = None  # optional text comment


@router.post("")
async def create_feedback(
    body: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if body.rating not in (1, -1):
        raise HTTPException(status_code=400, detail="Rating must be 1 (positive) or -1 (negative)")

    feedback = MessageFeedback(
        user_id=user.id,
        message_id=body.message_id,
        workflow_id=body.workflow_id,
        conversation_id=body.conversation_id,
        rating=body.rating,
        content=body.content,
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)

    return {
        "id": feedback.id,
        "rating": feedback.rating,
        "message_id": feedback.message_id,
        "created_at": feedback.created_at.isoformat(),
    }


@router.get("")
async def list_feedback(
    workflow_id: Optional[str] = Query(None),
    conversation_id: Optional[str] = Query(None),
    limit: int = Query(50, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(MessageFeedback)
        .where(MessageFeedback.user_id == user.id)
        .order_by(MessageFeedback.created_at.desc())
        .limit(limit)
    )
    if workflow_id:
        stmt = stmt.where(MessageFeedback.workflow_id == workflow_id)
    if conversation_id:
        stmt = stmt.where(MessageFeedback.conversation_id == conversation_id)

    result = await db.execute(stmt)
    items = result.scalars().all()

    return {
        "feedback": [
            {
                "id": f.id,
                "message_id": f.message_id,
                "rating": f.rating,
                "content": f.content,
                "workflow_id": f.workflow_id,
                "created_at": f.created_at.isoformat(),
            }
            for f in items
        ],
        "count": len(items),
    }


@router.get("/stats")
async def feedback_stats(
    workflow_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Aggregated feedback stats — total ratings, thumbs up %, thumbs down %."""
    stmt = select(
        func.count(MessageFeedback.id).label("total"),
        func.sum(func.case((MessageFeedback.rating == 1, 1), else_=0)).label("positive"),
        func.sum(func.case((MessageFeedback.rating == -1, 1), else_=0)).label("negative"),
    ).where(MessageFeedback.user_id == user.id)

    if workflow_id:
        stmt = stmt.where(MessageFeedback.workflow_id == workflow_id)

    result = await db.execute(stmt)
    row = result.one()

    total = row.total or 0
    positive = int(row.positive or 0)
    negative = int(row.negative or 0)

    return {
        "total": total,
        "positive": positive,
        "negative": negative,
        "positive_pct": round(positive / total * 100, 1) if total else 0,
        "negative_pct": round(negative / total * 100, 1) if total else 0,
    }


@router.delete("/{feedback_id}")
async def delete_feedback(
    feedback_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(MessageFeedback).where(
            MessageFeedback.id == feedback_id,
            MessageFeedback.user_id == user.id,
        )
    )
    fb = result.scalar_one_or_none()
    if not fb:
        raise HTTPException(status_code=404, detail="Feedback not found")

    await db.delete(fb)
    await db.commit()
    return {"deleted": True, "id": feedback_id}
