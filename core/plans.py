"""
Plan limits and enforcement.

`storage.models.Organization` already had `plan`, `max_workflows`, and
`max_executions_per_day` columns before this file existed — but nothing
in the codebase ever read them to actually block anything. An org on the
Free plan could create unlimited workflows and run unlimited executions;
the fields were decorative. This module is the part that was missing:
a real limits table and the functions that enforce it at the points that
matter (workflow activation, execution start, member invites, execution
history retrieval).

Solo/personal accounts (no org) are NOT limited by any of this — same
philosophy as api/middleware/rbac.py's role gating: these limits exist to
meter and monetize team usage, not to cripple someone using their own
account alone. Give a solo user Free-tier limits and you've built a
worse product for no monetization benefit (nobody is paying for their
own single-seat usage at these numbers anyway).
"""
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from storage.models import Organization, OrgPlan, Workflow, WorkflowStatus, Execution, User


class PlanLimits:
    def __init__(
        self,
        price_inr_per_month: int | None,  # None = custom/contact sales
        max_executions_per_month: int | None,  # None = custom
        max_active_workflows: int | None,  # None = unlimited
        max_users: int | None,  # None = custom
        execution_history_days: int | None,  # None = custom/unlimited
        integrations: str,  # "basic" | "standard" | "premium" | "custom"
        ai_workflow_builder: str,  # "limited" | "full"
        ai_agents: str,  # "none" | "limited" | "full"
        versioning: str,  # "none" | "basic" | "full"
        analytics: str,  # "basic" | "advanced" | "custom"
        rbac_audit_logs: bool,
        sso_saml: bool,  # "add-on" and "included" both map to True here — the add-on distinction is a billing/UI detail, not an enforcement one
        dedicated_workers: bool,
        on_premise: bool,
        support: str,  # "community" | "email" | "priority" | "dedicated"
    ):
        self.price_inr_per_month = price_inr_per_month
        self.max_executions_per_month = max_executions_per_month
        self.max_active_workflows = max_active_workflows
        self.max_users = max_users
        self.execution_history_days = execution_history_days
        self.integrations = integrations
        self.ai_workflow_builder = ai_workflow_builder
        self.ai_agents = ai_agents
        self.versioning = versioning
        self.analytics = analytics
        self.rbac_audit_logs = rbac_audit_logs
        self.sso_saml = sso_saml
        self.dedicated_workers = dedicated_workers
        self.on_premise = on_premise
        self.support = support


PLAN_LIMITS: dict[str, PlanLimits] = {
    "free": PlanLimits(
        price_inr_per_month=0, max_executions_per_month=500, max_active_workflows=5, max_users=1,
        execution_history_days=1, integrations="basic", ai_workflow_builder="limited", ai_agents="none",
        versioning="none", analytics="basic", rbac_audit_logs=False, sso_saml=False,
        dedicated_workers=False, on_premise=False, support="community",
    ),
    "starter": PlanLimits(
        price_inr_per_month=999, max_executions_per_month=10_000, max_active_workflows=25, max_users=2,
        execution_history_days=7, integrations="standard", ai_workflow_builder="full", ai_agents="limited",
        versioning="basic", analytics="basic", rbac_audit_logs=False, sso_saml=False,
        dedicated_workers=False, on_premise=False, support="email",
    ),
    "pro": PlanLimits(
        price_inr_per_month=3_499, max_executions_per_month=50_000, max_active_workflows=None, max_users=10,
        execution_history_days=30, integrations="standard", ai_workflow_builder="full", ai_agents="full",
        versioning="full", analytics="advanced", rbac_audit_logs=False, sso_saml=False,
        dedicated_workers=False, on_premise=False, support="priority",
    ),
    "business": PlanLimits(
        price_inr_per_month=12_999, max_executions_per_month=250_000, max_active_workflows=None, max_users=50,
        execution_history_days=90, integrations="premium", ai_workflow_builder="full", ai_agents="full",
        versioning="full", analytics="advanced", rbac_audit_logs=True, sso_saml=True,
        dedicated_workers=True, on_premise=False, support="priority",
    ),
    "enterprise": PlanLimits(
        price_inr_per_month=None, max_executions_per_month=None, max_active_workflows=None, max_users=None,
        execution_history_days=None, integrations="custom", ai_workflow_builder="full", ai_agents="full",
        versioning="full", analytics="custom", rbac_audit_logs=True, sso_saml=True,
        dedicated_workers=True, on_premise=True, support="dedicated",
    ),
}


def get_plan_limits(org: Organization | None) -> PlanLimits:
    """No org (solo/personal account) = unmetered, see module docstring."""
    if org is None:
        return PLAN_LIMITS["enterprise"]
    return PLAN_LIMITS.get(org.plan.value if hasattr(org.plan, "value") else org.plan, PLAN_LIMITS["free"])


async def _get_org(user: User, db: AsyncSession) -> Organization | None:
    if not user.org_id:
        return None
    result = await db.execute(select(Organization).where(Organization.id == user.org_id))
    return result.scalar_one_or_none()


async def _lock_org_for_limit_check(org_id: str, db: AsyncSession) -> None:
    """
    Serializes concurrent limit checks for the same org, without the
    deadlock risk of SELECT ... FOR UPDATE on the organizations row.

    FOR UPDATE was tried first and confirmed, under a real concurrency
    test, to deadlock: any ordinary INSERT referencing this org (a new
    workflow, a new execution) takes an implicit share lock on the
    organizations row for its foreign-key check, and two transactions
    that each did their own insert-then-FOR-UPDATE could end up in a
    circular wait on each other's locks (Postgres correctly detects and
    kills one with DeadlockDetectedError). A Postgres advisory lock is
    independent of ordinary row locks — it doesn't participate in that
    FK-check lock at all — so it serializes concurrent limit checks
    against each other without ever contending with a plain insert.
    Scoped to the current transaction (released automatically on
    commit/rollback, no manual unlock needed).
    """
    from sqlalchemy import text
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:org_id))"), {"org_id": org_id})


async def check_active_workflow_limit(user: User, db: AsyncSession) -> None:
    """
    Call before setting a workflow's status to active, WITHIN the same
    transaction that will then flip the status and commit. Serializes
    concurrent activation attempts for the same org via an advisory lock
    (see _lock_org_for_limit_check) — without this, N concurrent
    activation requests near the limit could all read "4 active, limit
    5" before any of them commits its own activation, and all N would
    pass, overshooting the cap.
    """
    org = await _get_org(user, db)
    if org is not None:
        await _lock_org_for_limit_check(org.id, db)
    limits = get_plan_limits(org)
    if limits.max_active_workflows is None:
        return

    result = await db.execute(
        select(func.count()).select_from(Workflow)
        .where(Workflow.owner_id == user.id, Workflow.status == WorkflowStatus.active)
    )
    active_count = result.scalar()
    if active_count >= limits.max_active_workflows:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Your {org.plan.value if org else 'current'} plan allows up to "
                f"{limits.max_active_workflows} active workflows. Deactivate one, or upgrade your plan."
            ),
        )


async def check_execution_limit(org_id: str | None, db: AsyncSession) -> None:
    """
    Call before creating a new Execution row, within the same
    transaction that will insert it. Raises PaymentRequired if the org's
    monthly execution count is already at/over its plan limit. Computed
    on the fly (COUNT query over the current month) rather than a
    separately maintained counter column — one less thing that can
    drift out of sync with reality, at the cost of one extra query per
    execution start, which is cheap relative to actually running a
    workflow.

    Serializes concurrent checks for the same org via an advisory lock
    (see _lock_org_for_limit_check) — a plain SELECT ... FOR UPDATE was
    tried first and confirmed, under a real concurrency test, to
    deadlock against the implicit FK-check lock any ordinary Execution
    insert takes on the same org row.
    """
    if not org_id:
        return  # solo account, unmetered — see module docstring
    await _lock_org_for_limit_check(org_id, db)
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    limits = get_plan_limits(org)
    if limits.max_executions_per_month is None:
        return

    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    count_result = await db.execute(
        select(func.count()).select_from(Execution)
        .join(Workflow, Workflow.id == Execution.workflow_id)
        .where(Workflow.org_id == org_id, Execution.created_at >= month_start)
    )
    count = count_result.scalar()
    if count >= limits.max_executions_per_month:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Your {org.plan.value} plan allows {limits.max_executions_per_month} "
                f"workflow executions per month, and you've used {count}. Upgrade your plan to continue."
            ),
        )


async def check_user_limit(user: User, db: AsyncSession) -> None:
    """
    Call before inviting a new member to an org, within the same
    transaction that will create the membership. Same race as
    check_active_workflow_limit/check_execution_limit — concurrent
    invite requests near the limit could all read "under limit" before
    any commits — closed the same way, with the advisory lock rather
    than FOR UPDATE (see _lock_org_for_limit_check's docstring for why
    FOR UPDATE deadlocks here).
    """
    org = await _get_org(user, db)
    if org is not None:
        await _lock_org_for_limit_check(org.id, db)
    limits = get_plan_limits(org)
    if limits.max_users is None:
        return

    result = await db.execute(select(func.count()).select_from(User).where(User.org_id == user.org_id))
    member_count = result.scalar()
    if member_count >= limits.max_users:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Your {org.plan.value if org else 'current'} plan allows up to "
                f"{limits.max_users} users. Remove a member, or upgrade your plan."
            ),
        )


async def execution_history_cutoff(user: User, db: AsyncSession) -> datetime | None:
    """Returns the earliest created_at a plan's execution history query should include, or None for unlimited."""
    org = await _get_org(user, db)
    limits = get_plan_limits(org)
    if limits.execution_history_days is None:
        return None
    return datetime.utcnow() - timedelta(days=limits.execution_history_days)


async def require_feature(user: User, db: AsyncSession, feature: str) -> None:
    """
    Gate a plan-tier feature (e.g. 'rbac_audit_logs', 'sso_saml') rather
    than a usage limit. `feature` must be a boolean attribute on
    PlanLimits.
    """
    org = await _get_org(user, db)
    limits = get_plan_limits(org)
    if not getattr(limits, feature, False):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"This feature requires a Business plan or above. Your current plan: {org.plan.value if org else 'personal'}.",
        )
