"""Triggers router."""
import uuid
import secrets
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from storage.database import get_db
from storage.models import Trigger, TriggerType, WebhookEndpoint, Workflow
from api.middleware.auth import get_current_user
from core.config import settings

router = APIRouter()


class TriggerCreate(BaseModel):
    workflow_id: str
    trigger_type: str
    provider: str
    event: str
    config: dict = {}
    credential_id: Optional[str] = None


@router.get("")
async def list_triggers(
    workflow_id: str = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    q = select(Trigger).join(Workflow).where(Workflow.owner_id == user.id)
    if workflow_id:
        q = q.where(Trigger.workflow_id == workflow_id)
    result = await db.execute(q)
    triggers = result.scalars().all()
    return {"triggers": [_serialize_trigger(t) for t in triggers]}


@router.post("", status_code=201)
async def create_trigger(
    body: TriggerCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    # Verify workflow ownership
    wf_result = await db.execute(
        select(Workflow).where(Workflow.id == body.workflow_id, Workflow.owner_id == user.id)
    )
    if not wf_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Workflow not found")

    trigger = Trigger(
        id=str(uuid.uuid4()),
        workflow_id=body.workflow_id,
        trigger_type=body.trigger_type,
        provider=body.provider,
        event=body.event,
        config=body.config,
        credential_id=body.credential_id,
    )
    db.add(trigger)

    # If webhook trigger, also create a WebhookEndpoint
    if body.trigger_type == TriggerType.webhook:
        path_token = secrets.token_urlsafe(24)
        webhook = WebhookEndpoint(
            id=str(uuid.uuid4()),
            path_token=path_token,
            workflow_id=body.workflow_id,
            trigger_id=trigger.id,
            secret=secrets.token_urlsafe(32),
        )
        db.add(webhook)
        await db.commit()
        await db.refresh(trigger)
        return {
            **_serialize_trigger(trigger),
            "webhook_url": f"{settings.APP_BASE_URL}/webhooks/{path_token}",
            "webhook_secret": webhook.secret,
        }

    await db.commit()
    await db.refresh(trigger)
    return _serialize_trigger(trigger)


@router.delete("/{trigger_id}", status_code=204)
async def delete_trigger(
    trigger_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(
        select(Trigger).join(Workflow).where(Trigger.id == trigger_id, Workflow.owner_id == user.id)
    )
    trigger = result.scalar_one_or_none()
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    await db.delete(trigger)
    await db.commit()


def _serialize_trigger(t: Trigger) -> dict:
    return {
        "id": t.id,
        "workflow_id": t.workflow_id,
        "trigger_type": t.trigger_type,
        "provider": t.provider,
        "event": t.event,
        "config": t.config,
        "credential_id": t.credential_id,
        "is_active": t.is_active,
        "last_triggered_at": t.last_triggered_at.isoformat() if t.last_triggered_at else None,
    }
