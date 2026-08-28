"""Organizations + members (multi-tenancy, RBAC)."""
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.auth import get_current_user
from api.middleware.rbac import require_permission
from core.audit import write_audit_log
from core.plans import check_user_limit, require_feature, get_plan_limits
from storage.database import get_db
from storage.models import Organization, OrgRole, User

router = APIRouter()


class OrgCreate(BaseModel):
    name: str
    plan: Optional[str] = "free"


class MemberInvite(BaseModel):
    email: str
    role: str = "viewer"


class MemberRoleUpdate(BaseModel):
    role: str


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


@router.post("", status_code=201)
async def create_org(
    body: OrgCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    org = Organization(name=body.name, slug=_slugify(body.name), plan=body.plan or "free")
    db.add(org)
    await db.flush()

    user.org_id = org.id
    user.role = OrgRole.owner
    await db.commit()
    await db.refresh(org)
    return {"id": org.id, "name": org.name, "slug": org.slug, "plan": org.plan}


@router.get("/current")
async def get_current_org(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.org_id:
        raise HTTPException(status_code=404, detail="You are not part of an organization")
    result = await db.execute(select(Organization).where(Organization.id == user.org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return {
        "id": org.id, "name": org.name, "slug": org.slug, "plan": org.plan,
        "max_workflows": org.max_workflows, "max_executions_per_day": org.max_executions_per_day,
        "settings": org.settings,
    }


@router.put("/settings")
async def update_org_settings(
    settings: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("org:settings")),
):
    result = await db.execute(select(Organization).where(Organization.id == user.org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    org.settings = settings
    await write_audit_log(db, request, user, "org.settings_update", "organization", org.id, {"settings": settings})
    await db.commit()
    return {"settings": org.settings}


@router.get("/members")
async def list_members(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("member:read")),
):
    result = await db.execute(select(User).where(User.org_id == user.org_id))
    members = result.scalars().all()
    return [{"id": m.id, "email": m.email, "role": m.role} for m in members]


@router.post("/members/invite")
async def invite_member(
    body: MemberInvite,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("member:invite")),
):
    valid_roles = {r.value for r in OrgRole}
    if body.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of {valid_roles}")

    await check_user_limit(user, db)

    result = await db.execute(select(User).where(User.email == body.email))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User with this email not found")

    target.org_id = user.org_id
    target.role = OrgRole(body.role)
    await write_audit_log(db, request, user, "member.invite", "user", target.id, {"role": body.role})
    await db.commit()
    return {"id": target.id, "email": target.email, "role": target.role}


@router.patch("/members/{member_id}/role")
async def change_member_role(
    member_id: str,
    body: MemberRoleUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("member:role")),
):
    valid_roles = {r.value for r in OrgRole}
    if body.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of {valid_roles}")

    result = await db.execute(select(User).where(User.id == member_id, User.org_id == user.org_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")

    target.role = OrgRole(body.role)
    await write_audit_log(db, request, user, "member.role_change", "user", target.id, {"role": body.role})
    await db.commit()
    return {"id": target.id, "email": target.email, "role": target.role}


@router.delete("/members/{member_id}", status_code=204)
async def remove_member(
    member_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("member:remove")),
):
    result = await db.execute(select(User).where(User.id == member_id, User.org_id == user.org_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")

    target.org_id = None
    target.role = None
    await write_audit_log(db, request, user, "member.remove", "user", member_id)
    await db.commit()


@router.get("/audit-log")
async def list_audit_log(
    limit: int = 100,
    action: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("audit:read")),
):
    """
    Gated two ways, matching the pricing table: role (admin/owner —
    require_permission("audit:read") above) AND plan tier (RBAC/Audit
    logs is a Business-plan feature — core/plans.py). A Pro-plan admin
    still can't see this; both conditions must hold.
    """
    await require_feature(user, db, "rbac_audit_logs")

    from storage.models import AuditLog
    stmt = select(AuditLog).where(AuditLog.org_id == user.org_id).order_by(AuditLog.created_at.desc()).limit(min(limit, 500))
    if action:
        stmt = stmt.where(AuditLog.action == action)
    result = await db.execute(stmt)
    entries = result.scalars().all()

    return [
        {
            "id": e.id, "user_id": e.user_id, "action": e.action,
            "resource_type": e.resource_type, "resource_id": e.resource_id,
            "meta": e.meta, "ip_address": e.ip_address, "created_at": e.created_at.isoformat(),
        } for e in entries
    ]
