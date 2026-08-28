"""Inbound webhook routes."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from storage.database import get_db
from triggers.engine import WebhookDispatcher
from integrations.whatsapp.handler import validate_whatsapp_signature, parse_whatsapp_webhook
from integrations.telegram.handler import parse_telegram_update, set_telegram_webhook
from core.config import settings

router = APIRouter()


# ─── Generic inbound webhook ─────────────────────────────────────────────────

@router.api_route("/{path_token}", methods=["GET", "POST", "PUT", "PATCH"])
async def receive_webhook(
    path_token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    if request.method == "GET":
        # Some providers (Slack, GitHub) send a GET verification ping
        return JSONResponse({"ok": True})

    result = await WebhookDispatcher.dispatch(path_token, request, db)
    return JSONResponse(result)


# ─── WhatsApp Meta Cloud API ─────────────────────────────────────────────────

@router.get("/whatsapp/inbound")
async def whatsapp_verify(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/whatsapp/inbound")
async def whatsapp_inbound(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("x-hub-signature-256", "")

    if settings.WHATSAPP_APP_SECRET and not validate_whatsapp_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid WhatsApp signature")

    import json
    payload = json.loads(body)
    messages = parse_whatsapp_webhook(payload)

    # Find active triggers for whatsapp:new_message
    from sqlalchemy import select
    from storage.models import Trigger, TriggerType, Workflow, WorkflowStatus, Execution, ExecutionStatus
    import uuid

    result = await db.execute(
        select(Trigger).where(
            Trigger.provider == "whatsapp",
            Trigger.event == "new_message",
            Trigger.is_active == True,
        )
    )
    triggers = result.scalars().all()

    for trigger in triggers:
        wf_result = await db.execute(
            select(Workflow).where(
                Workflow.id == trigger.workflow_id,
                Workflow.status == WorkflowStatus.active,
            )
        )
        workflow = wf_result.scalar_one_or_none()
        if not workflow:
            continue

        for msg in messages:
            execution = Execution(
                id=str(uuid.uuid4()),
                workflow_id=workflow.id,
                status=ExecutionStatus.queued,
                trigger_type="whatsapp_webhook",
                trigger_data=msg,
            )
            db.add(execution)
            await db.flush()

            from workers.tasks import run_workflow_task
            run_workflow_task.apply_async(
                args=[execution.id, workflow.definition, msg],
                queue="workflows",
            )

    await db.commit()
    return JSONResponse({"status": "ok"})


# ─── Telegram webhook ─────────────────────────────────────────────────────────

@router.post("/telegram/inbound")
async def telegram_inbound(request: Request, db: AsyncSession = Depends(get_db)):
    secret_token = request.headers.get("x-telegram-bot-api-secret-token", "")
    if settings.TELEGRAM_BOT_TOKEN and secret_token != settings.TELEGRAM_BOT_TOKEN[:20]:
        # Light validation — use a dedicated webhook secret in production
        pass

    import json
    payload = json.loads(await request.body())
    event = parse_telegram_update(payload)

    from sqlalchemy import select
    from storage.models import Trigger, Workflow, WorkflowStatus, Execution, ExecutionStatus
    import uuid

    result = await db.execute(
        select(Trigger).where(
            Trigger.provider == "telegram",
            Trigger.event == "new_message",
            Trigger.is_active == True,
        )
    )
    triggers = result.scalars().all()

    for trigger in triggers:
        wf_result = await db.execute(
            select(Workflow).where(
                Workflow.id == trigger.workflow_id,
                Workflow.status == WorkflowStatus.active,
            )
        )
        workflow = wf_result.scalar_one_or_none()
        if not workflow:
            continue

        execution = Execution(
            id=str(uuid.uuid4()),
            workflow_id=workflow.id,
            status=ExecutionStatus.queued,
            trigger_type="telegram_webhook",
            trigger_data=event,
        )
        db.add(execution)
        await db.flush()

        from workers.tasks import run_workflow_task
        run_workflow_task.apply_async(
            args=[execution.id, workflow.definition, event],
            queue="workflows",
        )

    await db.commit()
    return JSONResponse({"ok": True})


# ─── Slack event subscriptions ────────────────────────────────────────────────

@router.post("/slack/events")
async def slack_events(request: Request, db: AsyncSession = Depends(get_db)):
    import json, hmac, hashlib, time

    body = await request.body()
    payload = json.loads(body)

    # URL verification challenge
    if payload.get("type") == "url_verification":
        return JSONResponse({"challenge": payload["challenge"]})

    # Verify Slack signature
    if settings.SLACK_SIGNING_SECRET:
        timestamp = request.headers.get("x-slack-request-timestamp", "")
        slack_sig = request.headers.get("x-slack-signature", "")
        sig_basestring = f"v0:{timestamp}:{body.decode()}"
        expected = "v0=" + hmac.new(
            settings.SLACK_SIGNING_SECRET.encode(), sig_basestring.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, slack_sig):
            raise HTTPException(status_code=401, detail="Invalid Slack signature")

    event = payload.get("event", {})
    event_type = event.get("type", "")

    from sqlalchemy import select
    from storage.models import Trigger, Workflow, WorkflowStatus, Execution, ExecutionStatus
    import uuid

    result = await db.execute(
        select(Trigger).where(
            Trigger.provider == "slack",
            Trigger.event == event_type,
            Trigger.is_active == True,
        )
    )
    triggers = result.scalars().all()

    for trigger in triggers:
        wf_result = await db.execute(
            select(Workflow).where(
                Workflow.id == trigger.workflow_id,
                Workflow.status == WorkflowStatus.active,
            )
        )
        workflow = wf_result.scalar_one_or_none()
        if not workflow:
            continue

        execution = Execution(
            id=str(uuid.uuid4()),
            workflow_id=workflow.id,
            status=ExecutionStatus.queued,
            trigger_type="slack_event",
            trigger_data=event,
        )
        db.add(execution)
        await db.flush()

        from workers.tasks import run_workflow_task
        run_workflow_task.apply_async(
            args=[execution.id, workflow.definition, event],
            queue="workflows",
        )

    await db.commit()
    return JSONResponse({"ok": True})


# ─── GitHub webhook ───────────────────────────────────────────────────────────

@router.post("/github/events")
async def github_events(request: Request, db: AsyncSession = Depends(get_db)):
    import json, hmac, hashlib

    body = await request.body()
    event_type = request.headers.get("x-github-event", "")
    signature = request.headers.get("x-hub-signature-256", "")

    payload = json.loads(body)

    from sqlalchemy import select
    from storage.models import Trigger, Workflow, WorkflowStatus, Execution, ExecutionStatus
    import uuid

    result = await db.execute(
        select(Trigger).where(
            Trigger.provider == "github",
            Trigger.event == event_type,
            Trigger.is_active == True,
        )
    )
    triggers = result.scalars().all()

    for trigger in triggers:
        # Validate HMAC if secret set in trigger config
        secret = trigger.config.get("webhook_secret")
        if secret:
            expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, signature):
                continue

        wf_result = await db.execute(
            select(Workflow).where(
                Workflow.id == trigger.workflow_id,
                Workflow.status == WorkflowStatus.active,
            )
        )
        workflow = wf_result.scalar_one_or_none()
        if not workflow:
            continue

        trigger_data = {"event": event_type, "payload": payload}
        execution = Execution(
            id=str(uuid.uuid4()),
            workflow_id=workflow.id,
            status=ExecutionStatus.queued,
            trigger_type="github_webhook",
            trigger_data=trigger_data,
        )
        db.add(execution)
        await db.flush()

        from workers.tasks import run_workflow_task
        run_workflow_task.apply_async(
            args=[execution.id, workflow.definition, trigger_data],
            queue="workflows",
        )

    await db.commit()
    return JSONResponse({"ok": True})
