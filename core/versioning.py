"""Workflow versioning — snapshot, list, rollback, diff."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storage.models import Workflow, WorkflowVersion


async def snapshot_version(db: AsyncSession, workflow: Workflow, user_id: str, change_summary: str | None = None) -> WorkflowVersion:
    """Save the workflow's *current* state as a version row, then bump workflow.version."""
    version = WorkflowVersion(
        workflow_id=workflow.id,
        version=workflow.version,
        definition=workflow.definition,
        settings=workflow.settings or {},
        change_summary=change_summary,
        created_by=user_id,
    )
    db.add(version)
    workflow.version += 1
    return version


async def list_versions(db: AsyncSession, workflow_id: str) -> list[WorkflowVersion]:
    result = await db.execute(
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == workflow_id)
        .order_by(WorkflowVersion.version.desc())
    )
    return list(result.scalars().all())


async def get_version(db: AsyncSession, workflow_id: str, version: int) -> WorkflowVersion | None:
    result = await db.execute(
        select(WorkflowVersion).where(
            WorkflowVersion.workflow_id == workflow_id,
            WorkflowVersion.version == version,
        )
    )
    return result.scalar_one_or_none()


async def rollback_to_version(db: AsyncSession, workflow: Workflow, version: int, user_id: str) -> Workflow:
    target = await get_version(db, workflow.id, version)
    if not target:
        raise ValueError(f"Version {version} not found for workflow {workflow.id}")

    # snapshot current state first so rollback itself is reversible
    await snapshot_version(db, workflow, user_id, change_summary=f"Auto-save before rollback to v{version}")

    workflow.definition = target.definition
    workflow.settings = target.settings
    return workflow


def diff_versions(v1: WorkflowVersion, v2: WorkflowVersion) -> dict:
    nodes1 = {n["id"]: n for n in v1.definition.get("nodes", [])}
    nodes2 = {n["id"]: n for n in v2.definition.get("nodes", [])}

    added = [n for nid, n in nodes2.items() if nid not in nodes1]
    removed = [n for nid, n in nodes1.items() if nid not in nodes2]
    modified = [n for nid, n in nodes2.items() if nid in nodes1 and nodes1[nid] != n]

    return {"added_nodes": added, "removed_nodes": removed, "modified_nodes": modified}
