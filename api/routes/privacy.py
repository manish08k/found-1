"""
Privacy/GDPR-style endpoints: data export ("right to access") and account
deletion ("right to erasure"). These exist because PRIVACY_POLICY.md
promises them — a privacy policy that says "you can export or delete your
data" with no working endpoint behind it is worse than not promising it.

Design notes:
  - Export includes the user's own data: profile, workflow definitions,
    execution history, credential METADATA (never decrypted secrets —
    exporting someone's plaintext database passwords would itself be a
    security incident, not a privacy feature).
  - Deletion cascades through the DB's existing ON DELETE CASCADE
    constraints (workflows, credentials, refresh tokens all cascade from
    users.id — see storage/models.py) EXCEPT audit_logs, which are
    anonymized (user_id set to NULL) rather than deleted outright. This
    is the standard, defensible pattern for "right to erasure" vs.
    legitimate security/fraud-prevention record-keeping — the log entry
    "someone accessed credential X at time T" still has security value
    with the identity redacted; keeping the raw user_id after account
    deletion would not.
  - Deletion requires re-entering the password (not just being logged
    in) — same reasoning as any destructive-action confirmation: an
    already-open session/stolen bearer token shouldn't be enough on its
    own to permanently destroy an account.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from storage.database import get_db
from storage.models import User, Workflow, Execution, OAuthCredential, AuditLog
from api.middleware.auth import get_current_user, verify_password

router = APIRouter(prefix="/api/privacy", tags=["Privacy"])


class AccountDeletionRequest(BaseModel):
    password: str
    confirm: str  # must be exactly "DELETE MY ACCOUNT" — a typed confirmation, not just a checkbox


@router.get("/export")
async def export_my_data(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Everything AutoFlow holds about this account, as JSON. Credential
    entries include provider/label/creation date — never the decrypted
    secret itself (see credentials/envelope.py; there is no code path
    that decrypts a credential outside of an actual workflow node run).
    """
    workflows_result = await db.execute(select(Workflow).where(Workflow.owner_id == user.id))
    workflows = workflows_result.scalars().all()

    creds_result = await db.execute(select(OAuthCredential).where(OAuthCredential.user_id == user.id))
    creds = creds_result.scalars().all()

    workflow_ids = [w.id for w in workflows]
    executions = []
    if workflow_ids:
        exec_result = await db.execute(select(Execution).where(Execution.workflow_id.in_(workflow_ids)))
        executions = exec_result.scalars().all()

    audit_result = await db.execute(
        select(AuditLog).where(AuditLog.user_id == user.id).order_by(AuditLog.created_at.desc()).limit(1000)
    )
    audit_entries = audit_result.scalars().all()

    return {
        "exported_at": datetime.utcnow().isoformat(),
        "account": {
            "id": user.id,
            "email": user.email,
            "created_at": user.created_at.isoformat(),
            "mfa_enabled": user.mfa_enabled,
            "org_id": user.org_id,
            "role": user.role.value if user.role else None,
        },
        "workflows": [
            {
                "id": w.id, "name": w.name, "description": w.description,
                "status": w.status.value, "definition": w.definition,
                "created_at": w.created_at.isoformat(), "updated_at": w.updated_at.isoformat(),
            } for w in workflows
        ],
        "credentials": [
            {
                # Deliberately excludes `encrypted_token` — see module docstring.
                "id": c.id, "provider": c.provider, "label": c.label,
                "external_account_name": c.external_account_name,
                "created_at": c.created_at.isoformat(),
            } for c in creds
        ],
        "executions": [
            {
                "id": e.id, "workflow_id": e.workflow_id, "status": e.status.value,
                "trigger_type": e.trigger_type, "error": e.error,
                "started_at": e.started_at.isoformat() if e.started_at else None,
                "finished_at": e.finished_at.isoformat() if e.finished_at else None,
            } for e in executions
        ],
        "audit_log": [
            {
                "action": a.action, "resource_type": a.resource_type,
                "resource_id": a.resource_id, "created_at": a.created_at.isoformat(),
            } for a in audit_entries
        ],
    }


@router.delete("/account", status_code=204)
async def delete_my_account(
    body: AccountDeletionRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if body.confirm != "DELETE MY ACCOUNT":
        raise HTTPException(status_code=400, detail='Type "DELETE MY ACCOUNT" exactly to confirm')
    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect password")

    # Anonymize audit trail entries rather than deleting them — see
    # module docstring for why this is the correct pattern, not an
    # oversight.
    await db.execute(
        update(AuditLog).where(AuditLog.user_id == user.id).values(user_id=None, meta={"anonymized": True})
    )

    # Everything else cascades from this delete via ON DELETE CASCADE
    # foreign keys already defined in storage/models.py: workflows (and
    # their executions/triggers/schedules/versions), credentials, and
    # refresh tokens.
    await db.delete(user)
    await db.commit()
