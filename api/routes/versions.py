"""Workflow versioning — list, get, rollback, diff."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.auth import get_current_user
from core.versioning import diff_versions, get_version, list_versions, rollback_to_version, snapshot_version
from storage.database import get_db
from storage.models import User, Workflow

router = APIRouter()


async def _get_owned_workflow(workflow_id: str, user: User, db: AsyncSession) -> Workflow:
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id, Workflow.owner_id == user.id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.get("/{workflow_id}/versions")
async def get_versions(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _get_owned_workflow(workflow_id, user, db)
    versions = await list_versions(db, workflow_id)
    return [
        {"version": v.version, "change_summary": v.change_summary,
         "created_by": v.created_by, "created_at": v.created_at.isoformat()}
        for v in versions
    ]


@router.get("/{workflow_id}/versions/{version}")
async def get_one_version(
    workflow_id: str,
    version: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _get_owned_workflow(workflow_id, user, db)
    v = await get_version(db, workflow_id, version)
    if not v:
        raise HTTPException(status_code=404, detail="Version not found")
    return {
        "version": v.version, "definition": v.definition, "settings": v.settings,
        "change_summary": v.change_summary, "created_at": v.created_at.isoformat(),
    }


@router.post("/{workflow_id}/versions/{version}/rollback")
async def rollback(
    workflow_id: str,
    version: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workflow = await _get_owned_workflow(workflow_id, user, db)
    try:
        await rollback_to_version(db, workflow, version, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await db.commit()
    await db.refresh(workflow)
    return {"id": workflow.id, "version": workflow.version, "definition": workflow.definition}


@router.get("/{workflow_id}/versions/diff")
async def diff(
    workflow_id: str,
    v1: int = Query(...),
    v2: int = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _get_owned_workflow(workflow_id, user, db)
    ver1 = await get_version(db, workflow_id, v1)
    ver2 = await get_version(db, workflow_id, v2)
    if not ver1 or not ver2:
        raise HTTPException(status_code=404, detail="Version(s) not found")
    return diff_versions(ver1, ver2)
