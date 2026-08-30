"""
AI Workflow Builder — generate, validate, and apply workflow graphs from prompts.
"""
import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.auth import get_current_user
from storage.database import get_db
from storage.models import Workflow, WorkflowStatus, User

log = structlog.get_logger(__name__)

router = APIRouter()


class GenerateRequest(BaseModel):
    prompt: str
    workflow_id: Optional[str] = None  # modify existing workflow


class ApplyRequest(BaseModel):
    workflow_id: Optional[str] = None  # update existing, or None to create new
    name: Optional[str] = None
    nodes: list[dict]
    edges: list[dict]


class ValidateRequest(BaseModel):
    nodes: list[dict]
    edges: list[dict]


@router.post("/generate")
async def generate_workflow(
    body: GenerateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate a workflow graph from a natural language prompt."""
    from core.workflow_generator import generate_workflow_from_prompt

    existing_workflow = None
    if body.workflow_id:
        result = await db.execute(
            select(Workflow).where(
                Workflow.id == body.workflow_id,
                Workflow.owner_id == user.id,
            )
        )
        wf = result.scalar_one_or_none()
        if wf:
            existing_workflow = wf.definition

    try:
        proposal = await generate_workflow_from_prompt(
            prompt=body.prompt,
            existing_workflow=existing_workflow,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error("ai_builder_generate_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")

    # Validate the generated graph
    from core.workflow_generator import validate_workflow_graph
    validation = validate_workflow_graph(
        proposal.get("nodes", []),
        proposal.get("edges", []),
    )

    return {
        "nodes": proposal.get("nodes", []),
        "edges": proposal.get("edges", []),
        "explanation": proposal.get("explanation", ""),
        "validation": validation,
    }


@router.post("/apply")
async def apply_workflow(
    body: ApplyRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Apply a proposed workflow to create or update a real workflow."""
    # Validate first
    from core.workflow_generator import validate_workflow_graph
    validation = validate_workflow_graph(body.nodes, body.edges)

    if not validation["valid"]:
        raise HTTPException(
            status_code=400,
            detail={"message": "Invalid workflow graph", "errors": validation["errors"]},
        )

    definition = {"nodes": body.nodes, "edges": body.edges}

    if body.workflow_id:
        # Update existing workflow
        result = await db.execute(
            select(Workflow).where(
                Workflow.id == body.workflow_id,
                Workflow.owner_id == user.id,
            )
        )
        wf = result.scalar_one_or_none()
        if not wf:
            raise HTTPException(status_code=404, detail="Workflow not found")

        # Snapshot current version before modifying
        from core.versioning import snapshot_version
        await snapshot_version(db, wf, user.id, change_summary="AI builder update")

        wf.definition = definition
        if body.name:
            wf.name = body.name
        await db.commit()
        await db.refresh(wf)

        return {
            "workflow_id": wf.id,
            "name": wf.name,
            "action": "updated",
            "version": wf.version,
        }
    else:
        # Create new workflow
        name = body.name or "AI-Generated Workflow"
        wf = Workflow(
            id=str(uuid.uuid4()),
            owner_id=user.id,
            org_id=user.org_id,
            name=name,
            definition=definition,
            status=WorkflowStatus.inactive,
        )
        db.add(wf)
        await db.commit()
        await db.refresh(wf)

        return {
            "workflow_id": wf.id,
            "name": wf.name,
            "action": "created",
            "version": wf.version,
        }


@router.post("/validate")
async def validate_workflow(
    body: ValidateRequest,
    user: User = Depends(get_current_user),
):
    """Validate a proposed workflow graph for correctness."""
    from core.workflow_generator import validate_workflow_graph
    result = validate_workflow_graph(body.nodes, body.edges)
    return result
