"""Workflow CRUD + activate/deactivate + manual trigger."""
import uuid
from typing import Any, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from storage.database import get_db, get_db_read
from storage.models import Execution, ExecutionStatus, Workflow, WorkflowStatus
from api.middleware.auth import get_current_user
from api.middleware.rbac import check_write_db_permission
from core.plans import check_active_workflow_limit, check_execution_limit
from core.marketplace import publish_item

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
    db: AsyncSession = Depends(get_db_read),
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
    check_write_db_permission(body.definition.model_dump(), user)
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
    workflow = await _get_owned_workflow(workflow_id, user.id, db)
    if body.definition is not None:
        check_write_db_permission(body.definition.model_dump(), user)

    # Auto-snapshot current version before modifying
    if body.definition is not None and workflow.definition:
        from core.versioning import snapshot_version
        change_parts = []
        if body.name and body.name != workflow.name:
            change_parts.append(f"renamed to '{body.name}'")
        if body.definition:
            change_parts.append("definition updated")
        summary = "; ".join(change_parts) if change_parts else "workflow updated"
        await snapshot_version(db, workflow, user.id, change_summary=summary)

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
    await check_active_workflow_limit(user, db)
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
    await check_execution_limit(workflow.org_id, db)

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


class PublishAsTemplateRequest(BaseModel):
    name: Optional[str] = None          # defaults to the workflow name
    description: Optional[str] = None
    category: Optional[str] = None
    tags: list[str] = []


@router.post("/{workflow_id}/publish-as-template", status_code=201)
async def publish_as_template(
    workflow_id: str,
    body: PublishAsTemplateRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Publish the current workflow definition to the marketplace as a reusable template."""
    workflow = await _get_owned_workflow(workflow_id, user.id, db)
    name = body.name or workflow.name
    description = body.description or workflow.description or ""
    # Strip credential_id from every node before publishing — credentials
    # are personal and must not be included in a shared template.
    definition = dict(workflow.definition or {})
    nodes = []
    for node in definition.get("nodes", []):
        n = dict(node)
        n.pop("credential_id", None)
        nodes.append(n)
    definition["nodes"] = nodes
    try:
        item = await publish_item(
            db, user.org_id, name, description,
            body.category, body.tags, "template", definition,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    return {"slug": item.slug, "name": item.name}


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
        "status": w.status.value if hasattr(w.status, 'value') else w.status,
        "definition": w.definition,
        "settings": w.settings,
        "created_at": w.created_at.isoformat(),
        "updated_at": w.updated_at.isoformat(),
    }
