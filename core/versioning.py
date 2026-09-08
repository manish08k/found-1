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

    nodes_added = [n for nid, n in nodes2.items() if nid not in nodes1]
    nodes_removed = [n for nid, n in nodes1.items() if nid not in nodes2]
    nodes_changed = [n for nid, n in nodes2.items() if nid in nodes1 and nodes1[nid] != n]

    # Build per-node config change details for modified nodes
    config_changes: dict = {}
    for n in nodes_changed:
        nid = n["id"]
        old_data = nodes1[nid].get("data", {})
        new_data = n.get("data", {})
        changes: dict = {}
        all_keys = set(old_data) | set(new_data)
        for key in all_keys:
            old_val = old_data.get(key)
            new_val = new_data.get(key)
            if old_val != new_val:
                changes[key] = {"old": old_val, "new": new_val}
        if changes:
            config_changes[nid] = changes

    # Edge diff
    def edge_key(e: dict) -> str:
        return f"{e.get('source', '')}→{e.get('target', '')}"

    edges1 = {edge_key(e): e for e in v1.definition.get("edges", [])}
    edges2 = {edge_key(e): e for e in v2.definition.get("edges", [])}
    edges_added = [e for k, e in edges2.items() if k not in edges1]
    edges_removed = [e for k, e in edges1.items() if k not in edges2]

    return {
        "nodes_added": nodes_added,
        "nodes_removed": nodes_removed,
        "nodes_changed": nodes_changed,
        "edges_added": edges_added,
        "edges_removed": edges_removed,
        "config_changes": config_changes,
        "summary": {
            "added": len(nodes_added),
            "removed": len(nodes_removed),
            "changed": len(nodes_changed),
            "edges_added": len(edges_added),
            "edges_removed": len(edges_removed),
        },
    }
