"""Audit logging helper."""
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from storage.models import AuditLog


async def write_audit_log(
    db: AsyncSession,
    request: Request,
    user,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    meta: dict | None = None,
) -> None:
    entry = AuditLog(
        org_id=getattr(user, "org_id", None),
        user_id=getattr(user, "id", None),
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        meta=meta or {},
        ip_address=request.client.host if request.client else None,
    )
    db.add(entry)
    # Caller is responsible for commit (usually piggybacks on the route's own commit).
