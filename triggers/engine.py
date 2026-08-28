"""
Trigger system.

WebhookDispatcher: receives inbound webhooks, validates HMAC,
  fires the correct workflow.

PollingEngine: runs on a schedule, checks sources (IMAP, RSS, etc.),
  fires workflows when new data arrives.
"""
import hashlib
import hmac
import json
import uuid
from datetime import datetime
from typing import Any

import structlog
from fastapi import HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from storage.models import (
    Execution, ExecutionStatus, Trigger, TriggerType, WebhookEndpoint, Workflow, WorkflowStatus
)
from storage.database import db_context

log = structlog.get_logger(__name__)


# ─── Webhook Dispatcher ───────────────────────────────────────────────────────

class WebhookDispatcher:

    @staticmethod
    async def dispatch(path_token: str, request: Request, db: AsyncSession) -> dict:
        # Look up endpoint
        result = await db.execute(
            select(WebhookEndpoint).where(
                WebhookEndpoint.path_token == path_token,
                WebhookEndpoint.is_active == True,
            )
        )
        endpoint = result.scalar_one_or_none()
        if not endpoint:
            raise HTTPException(status_code=404, detail="Webhook not found")

        body = await request.body()
        headers = dict(request.headers)

        # Signature validation
        if endpoint.secret:
            WebhookDispatcher._validate_signature(body, endpoint.secret, headers)

        payload = {}
        try:
            payload = json.loads(body)
        except Exception:
            payload = {"raw": body.decode(errors="replace")}

        # Load workflow
        wf_result = await db.execute(
            select(Workflow).where(
                Workflow.id == endpoint.workflow_id,
                Workflow.status == WorkflowStatus.active,
            )
        )
        workflow = wf_result.scalar_one_or_none()
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found or inactive")

        execution = await WebhookDispatcher._create_execution(
            workflow, trigger_type="webhook", trigger_data={
                "headers": headers,
                "payload": payload,
                "path_token": path_token,
            }, db=db
        )

        # Dispatch to Celery
        from workers.tasks import run_workflow_task
        run_workflow_task.apply_async(
            args=[execution.id, workflow.definition, execution.trigger_data],
            queue="workflows",
        )

        return {"execution_id": execution.id, "status": "queued"}

    @staticmethod
    def _validate_signature(body: bytes, secret: str, headers: dict) -> None:
        """Validates GitHub-style X-Hub-Signature-256 or generic X-Signature."""
        sig_header = (
            headers.get("x-hub-signature-256")
            or headers.get("x-signature")
            or headers.get("x-autoflow-signature")
        )
        if not sig_header:
            raise HTTPException(status_code=401, detail="Missing webhook signature")

        expected = "sha256=" + hmac.new(
            secret.encode(), body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, sig_header):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    @staticmethod
    async def _create_execution(
        workflow: Workflow,
        trigger_type: str,
        trigger_data: dict,
        db: AsyncSession,
    ) -> Execution:
        execution = Execution(
            id=str(uuid.uuid4()),
            workflow_id=workflow.id,
            status=ExecutionStatus.queued,
            trigger_type=trigger_type,
            trigger_data=trigger_data,
        )
        db.add(execution)
        await db.flush()
        return execution


# ─── Polling Engine ───────────────────────────────────────────────────────────

POLLING_HANDLERS: dict = {}


def register_poller(provider: str, event: str):
    """Decorator to register a polling handler."""
    def decorator(fn):
        POLLING_HANDLERS[f"{provider}:{event}"] = fn
        return fn
    return decorator


async def run_all_pollers() -> None:
    """Called by Celery beat every 60 seconds."""
    async with db_context() as db:
        result = await db.execute(
            select(Trigger).where(
                Trigger.trigger_type == TriggerType.polling,
                Trigger.is_active == True,
            )
        )
        triggers = result.scalars().all()

        for trigger in triggers:
            key = f"{trigger.provider}:{trigger.event}"
            handler = POLLING_HANDLERS.get(key)
            if not handler:
                log.warning("no_polling_handler", key=key)
                continue

            try:
                items = await handler(trigger.config, trigger.credential_id, db)
                if items:
                    wf_result = await db.execute(
                        select(Workflow).where(
                            Workflow.id == trigger.workflow_id,
                            Workflow.status == WorkflowStatus.active,
                        )
                    )
                    workflow = wf_result.scalar_one_or_none()
                    if workflow:
                        for item in items:
                            execution = await WebhookDispatcher._create_execution(
                                workflow, trigger_type="polling",
                                trigger_data={"item": item, "trigger_id": trigger.id},
                                db=db,
                            )
                            from workers.tasks import run_workflow_task
                            run_workflow_task.apply_async(
                                args=[execution.id, workflow.definition, execution.trigger_data],
                                queue="workflows",
                            )

                trigger.last_triggered_at = datetime.utcnow()
                await db.flush()

            except Exception as exc:
                log.error("polling_failed", trigger_id=trigger.id, key=key, error=str(exc))

        await db.commit()
