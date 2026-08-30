"""
Policy / Guardrails — CRUD and testing for organizational execution policies.
"""
import json
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.auth import get_current_user
from storage.database import get_db
from storage.models import Policy, User

log = structlog.get_logger(__name__)

router = APIRouter()


class PolicyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True
    rules: list[dict] = []
    action: str = "block"  # block | warn | require_approval


class PolicyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    rules: Optional[list[dict]] = None
    action: Optional[str] = None


class PolicyTestRequest(BaseModel):
    workflow: dict  # {"nodes": [...], "edges": [...]}
    trigger_data: dict = {}


def _serialize(p: Policy) -> dict:
    return {
        "id": p.id,
        "org_id": p.org_id,
        "name": p.name,
        "description": p.description,
        "is_active": p.is_active,
        "rules": p.rules,
        "action": p.action,
        "created_by": p.created_by,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


@router.get("")
async def list_policies(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all policies for the user's organization."""
    stmt = select(Policy).order_by(Policy.created_at.desc())
    if user.org_id:
        stmt = stmt.where(Policy.org_id == user.org_id)
    else:
        stmt = stmt.where(Policy.created_by == user.id)

    result = await db.execute(stmt)
    policies = result.scalars().all()
    return {"policies": [_serialize(p) for p in policies]}


@router.post("", status_code=201)
async def create_policy(
    body: PolicyCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new policy."""
    if body.action not in ("block", "warn", "require_approval"):
        raise HTTPException(status_code=400, detail="action must be 'block', 'warn', or 'require_approval'")

    # Validate rule types
    valid_types = {"node_allowlist", "node_denylist", "credential_restriction",
                   "keyword_block", "require_approval", "rate_limit"}
    for rule in body.rules:
        if rule.get("type") not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid rule type '{rule.get('type')}'. Must be one of: {valid_types}",
            )

    policy = Policy(
        org_id=user.org_id,
        name=body.name,
        description=body.description,
        is_active=body.is_active,
        rules=body.rules,
        action=body.action,
        created_by=user.id,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return _serialize(policy)


@router.get("/{policy_id}")
async def get_policy(
    policy_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    policy = await _get_policy(policy_id, user, db)
    return _serialize(policy)


@router.patch("/{policy_id}")
async def update_policy(
    policy_id: str,
    body: PolicyUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    policy = await _get_policy(policy_id, user, db)

    if body.name is not None:
        policy.name = body.name
    if body.description is not None:
        policy.description = body.description
    if body.is_active is not None:
        policy.is_active = body.is_active
    if body.rules is not None:
        policy.rules = body.rules
    if body.action is not None:
        if body.action not in ("block", "warn", "require_approval"):
            raise HTTPException(status_code=400, detail="Invalid action")
        policy.action = body.action

    await db.commit()
    await db.refresh(policy)
    return _serialize(policy)


@router.delete("/{policy_id}")
async def delete_policy(
    policy_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    policy = await _get_policy(policy_id, user, db)
    await db.delete(policy)
    await db.commit()
    return {"deleted": True, "id": policy_id}


@router.post("/{policy_id}/test")
async def test_policy(
    policy_id: str,
    body: PolicyTestRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Test a policy against sample workflow data."""
    policy = await _get_policy(policy_id, user, db)

    from core.policy_engine import check_policies

    # Build a workflow dict with org_id
    workflow = dict(body.workflow)
    workflow["org_id"] = user.org_id

    execution_context = {
        "org_id": user.org_id,
        "trigger_data": body.trigger_data,
    }

    result = await check_policies(workflow, execution_context, db)
    return {
        "policy_name": policy.name,
        **result,
    }


async def _get_policy(policy_id: str, user: User, db: AsyncSession) -> Policy:
    """Load a policy and verify access."""
    result = await db.execute(select(Policy).where(Policy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    # Check access: org member or creator
    if policy.org_id and user.org_id and policy.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="Policy not found")
    if not policy.org_id and policy.created_by != user.id:
        raise HTTPException(status_code=404, detail="Policy not found")

    return policy
