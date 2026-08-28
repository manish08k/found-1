"""
Billing routes — the plan catalog (matches the pricing table), a usage
endpoint, and real Stripe subscription billing (Checkout Sessions +
webhook-driven plan sync, core/stripe_billing.py).
"""
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.auth import get_current_user
from core.audit import write_audit_log
from core.config import settings
from core.plans import PLAN_LIMITS, get_plan_limits
from core.stripe_billing import create_checkout_session, verify_webhook_signature, apply_webhook_event, BillingNotConfigured
from storage.database import get_db
from storage.models import User, Organization, Workflow, WorkflowStatus, Execution

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/billing", tags=["Billing"])


def _limits_to_dict(plan_id: str, limits) -> dict:
    return {
        "plan": plan_id,
        "price_inr_per_month": limits.price_inr_per_month,  # null = custom/contact sales
        "max_executions_per_month": limits.max_executions_per_month,  # null = custom
        "max_active_workflows": limits.max_active_workflows,  # null = unlimited
        "max_users": limits.max_users,  # null = custom
        "execution_history_days": limits.execution_history_days,  # null = custom
        "integrations": limits.integrations,
        "ai_workflow_builder": limits.ai_workflow_builder,
        "ai_agents": limits.ai_agents,
        "versioning": limits.versioning,
        "analytics": limits.analytics,
        "rbac_audit_logs": limits.rbac_audit_logs,
        "sso_saml": limits.sso_saml,
        "dedicated_workers": limits.dedicated_workers,
        "on_premise": limits.on_premise,
        "support": limits.support,
    }


@router.get("/plans")
async def list_plans(response: Response):
    """Public — no auth required, this is pricing-page content. Static per-deploy, safe to cache."""
    response.headers["Cache-Control"] = "public, max-age=300"
    order = ["free", "starter", "pro", "business", "enterprise"]
    return {"plans": [_limits_to_dict(p, PLAN_LIMITS[p]) for p in order]}


@router.get("/usage")
async def get_usage(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    org = None
    if user.org_id:
        result = await db.execute(select(Organization).where(Organization.id == user.org_id))
        org = result.scalar_one_or_none()

    limits = get_plan_limits(org)
    plan_id = org.plan.value if org else "enterprise"  # solo accounts are treated as unmetered, not literally "on the enterprise plan" — see core/plans.py's docstring; surfaced here as-is so the frontend can label it "Personal (unmetered)" rather than showing a real tier name

    active_workflows = 0
    executions_this_month = 0
    member_count = 1

    if user.org_id:
        wf_count_result = await db.execute(
            select(func.count()).select_from(Workflow)
            .where(Workflow.org_id == user.org_id, Workflow.status == WorkflowStatus.active)
        )
        active_workflows = wf_count_result.scalar()

        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        exec_count_result = await db.execute(
            select(func.count()).select_from(Execution)
            .join(Workflow, Workflow.id == Execution.workflow_id)
            .where(Workflow.org_id == user.org_id, Execution.created_at >= month_start)
        )
        executions_this_month = exec_count_result.scalar()

        member_count_result = await db.execute(select(func.count()).select_from(User).where(User.org_id == user.org_id))
        member_count = member_count_result.scalar()
    else:
        wf_count_result = await db.execute(
            select(func.count()).select_from(Workflow)
            .where(Workflow.owner_id == user.id, Workflow.status == WorkflowStatus.active)
        )
        active_workflows = wf_count_result.scalar()

    return {
        "plan": plan_id,
        "is_personal_account": user.org_id is None,
        "usage": {
            "active_workflows": {"used": active_workflows, "limit": limits.max_active_workflows},
            "executions_this_month": {"used": executions_this_month, "limit": limits.max_executions_per_month},
            "users": {"used": member_count, "limit": limits.max_users},
        },
        "limits": _limits_to_dict(plan_id, limits),
    }


class UpgradeRequest(BaseModel):
    target_plan: str
    note: str | None = None


class CheckoutRequest(BaseModel):
    target_plan: str  # starter | pro | business — Free needs no checkout, Enterprise is sales-assisted


@router.post("/checkout")
async def checkout(
    body: CheckoutRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Creates a real Stripe Checkout Session and returns its URL for the
    frontend to redirect to. Requires this deployment to have a real
    Stripe merchant account configured (STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET, and the three STRIPE_PRICE_ID_* settings —
    core/config.py). Without those set, this returns 501 with a clear
    reason rather than a fake success — see BillingNotConfigured.
    """
    if not user.org_id:
        raise HTTPException(status_code=400, detail="Create or join an organization before subscribing to a paid plan")

    org_result = await db.execute(select(Organization).where(Organization.id == user.org_id))
    org = org_result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    base_url = settings.FRONTEND_URL or settings.APP_BASE_URL
    try:
        checkout_url = await create_checkout_session(
            org=org,
            user_email=user.email,
            target_plan=body.target_plan,
            success_url=f"{base_url}/?billing=success",
            cancel_url=f"{base_url}/?billing=cancelled",
        )
    except BillingNotConfigured as e:
        raise HTTPException(status_code=501, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await write_audit_log(db, request, user, "billing.checkout_started", "organization", org.id, {"target_plan": body.target_plan})
    await db.commit()
    return {"checkout_url": checkout_url}


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Stripe calls this directly (configure the URL in your Stripe
    dashboard's webhook settings) — no user auth here, Stripe
    authenticates itself via the signature in the Stripe-Signature
    header instead, verified against the raw request body.

    CRITICAL: reads request.body() (raw bytes) rather than a parsed
    Pydantic model — Stripe's signature is computed over the exact raw
    bytes it sent, and re-serializing a parsed-then-re-dumped JSON body
    would almost certainly produce different bytes (key order,
    whitespace) and fail verification even for a genuine, unmodified
    Stripe request.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = verify_webhook_signature(payload, sig_header)
    except BillingNotConfigured as e:
        raise HTTPException(status_code=501, detail=str(e))
    except ValueError as e:
        log.warning("stripe_webhook_rejected", reason=str(e))
        raise HTTPException(status_code=400, detail=f"Webhook verification failed: {e}")

    await apply_webhook_event(event, db)
    await db.commit()
    return {"received": True}


@router.post("/upgrade-request")
async def request_upgrade(
    body: UpgradeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Fallback path for when this deployment doesn't have a Stripe merchant
    account configured yet (see /checkout above for the real path once
    it does), and for Enterprise (sales-assisted, not self-serve
    checkout by design — matches the pricing table's "Custom"/"Contact
    Sales" framing). Records the request in the org's audit log so a
    real person can follow up; does not fake a completed purchase.
    """
    if body.target_plan not in PLAN_LIMITS:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {body.target_plan}")

    await write_audit_log(
        db, request, user, "billing.upgrade_requested", "organization", user.org_id,
        {"target_plan": body.target_plan, "note": body.note},
    )
    await db.commit()
    return {
        "status": "requested",
        "message": "Upgrade request recorded. Our team will follow up to complete this.",
    }
