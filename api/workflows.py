"""Workflow CRUD + activate/deactivate + manual trigger."""
import uuid
from typing import Any, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from storage.database import get_db
from storage.models import Execution, ExecutionStatus, Workflow, WorkflowStatus
from api.middleware.auth import get_current_user

router = APIRouter()


# ── Workflow definition schema ────────────────────────────────────────────────

class RetryConfig(BaseModel):
    max_attempts: int = Field(default=1, ge=1, le=10)
    wait_min: int = Field(default=1, ge=0)
    wait_max: int = Field(default=60, ge=0)


class NodeDefinition(BaseModel):
    id: str = Field(..., min_length=1, max_length=128)
    type: str = Field(..., min_length=1, max_length=64)
    config: dict[str, Any] = Field(default_factory=dict)
    credential_id: Optional[str] = None
    required: bool = True
    retry: RetryConfig = Field(default_factory=RetryConfig)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class EdgeDefinition(BaseModel):
    source: str = Field(..., min_length=1, max_length=128)
    target: str = Field(..., min_length=1, max_length=128)


class WorkflowDefinition(BaseModel):
    nodes: list[NodeDefinition] = Field(default_factory=list)
    edges: list[EdgeDefinition] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_edge_references(self) -> "WorkflowDefinition":
        node_ids = {n.id for n in self.nodes}
        for edge in self.edges:
            if edge.source not in node_ids:
                raise ValueError(f"Edge source '{edge.source}' not in nodes")
            if edge.target not in node_ids:
                raise ValueError(f"Edge target '{edge.target}' not in nodes")
        return self


# ── Request / response models ─────────────────────────────────────────────────


class WorkflowCreate(BaseModel):
    name: str
    description: Optional[str] = None
    definition: WorkflowDefinition = Field(default_factory=WorkflowDefinition)
    settings: dict[str, Any] = Field(default_factory=dict)


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    definition: Optional[WorkflowDefinition] = None
    settings: Optional[dict[str, Any]] = None


@router.get("")
async def list_workflows(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Workflow)
        .where(Workflow.owner_id == user.id)
        .order_by(Workflow.updated_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    workflows = result.scalars().all()

    total_result = await db.execute(
        select(func.count()).select_from(Workflow).where(Workflow.owner_id == user.id)
    )
    total = total_result.scalar()

    return {
        "workflows": [_serialize_workflow(w) for w in workflows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("", status_code=201)
async def create_workflow(
    body: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    workflow = Workflow(
        id=str(uuid.uuid4()),
        owner_id=user.id,
        name=body.name,
        description=body.description,
        definition=body.definition.model_dump(),
        settings=body.settings or {},
        status=WorkflowStatus.inactive,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return _serialize_workflow(workflow)


@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    workflow = await _get_owned_workflow(workflow_id, user.id, db)
    return _serialize_workflow(workflow)


@router.patch("/{workflow_id}")
async def update_workflow(
    workflow_id: str,
    body: WorkflowUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    from core.versioning import snapshot_version

    workflow = await _get_owned_workflow(workflow_id, user.id, db)
    if body.definition is not None:
        # Snapshot the pre-edit state so it can be rolled back to.
        await snapshot_version(db, workflow, user.id, change_summary="Edited via API")
    if body.name is not None:
        workflow.name = body.name
    if body.description is not None:
        workflow.description = body.description
    if body.definition is not None:
        workflow.definition = body.definition.model_dump()
    if body.settings is not None:
        workflow.settings = body.settings
    await db.commit()
    await db.refresh(workflow)
    return _serialize_workflow(workflow)


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    workflow = await _get_owned_workflow(workflow_id, user.id, db)
    await db.delete(workflow)
    await db.commit()


@router.post("/{workflow_id}/activate")
async def activate_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    workflow = await _get_owned_workflow(workflow_id, user.id, db)
    workflow.status = WorkflowStatus.active
    await db.commit()
    return {"status": "active"}


@router.post("/{workflow_id}/deactivate")
async def deactivate_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    workflow = await _get_owned_workflow(workflow_id, user.id, db)
    workflow.status = WorkflowStatus.inactive
    await db.commit()
    return {"status": "inactive"}


@router.post("/{workflow_id}/execute")
async def manual_execute(
    workflow_id: str,
    trigger_data: dict = {},
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    workflow = await _get_owned_workflow(workflow_id, user.id, db)

    execution = Execution(
        id=str(uuid.uuid4()),
        workflow_id=workflow_id,
        status=ExecutionStatus.queued,
        trigger_type="manual",
        trigger_data=trigger_data,
    )
    db.add(execution)
    await db.commit()

    from workers.tasks import run_workflow_task
    run_workflow_task.apply_async(
        args=[execution.id, workflow.definition, trigger_data],
        queue="workflows",
    )
    return {"execution_id": execution.id, "status": "queued"}


async def _get_owned_workflow(workflow_id: str, user_id: str, db: AsyncSession) -> Workflow:
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.owner_id == user_id)
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


def _serialize_workflow(w: Workflow) -> dict:
    return {
        "id": w.id,
        "name": w.name,
        "description": w.description,
        "status": w.status,
        "definition": w.definition,
        "settings": w.settings,
        "created_at": w.created_at.isoformat(),
        "updated_at": w.updated_at.isoformat(),
    }
