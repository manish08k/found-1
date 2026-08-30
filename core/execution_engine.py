"""
Workflow Execution Engine.

- Topological sort of nodes
- Sequential + parallel execution (nodes with no dependencies run in parallel)
- Per-node retry with exponential backoff
- Full execution log persisted to DB
- Node types dispatch to integration handlers
"""
import asyncio
import time
import traceback
from collections import defaultdict, deque
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from storage.models import Execution, ExecutionStatus, Workflow
from storage.database import db_context
from core.config import settings

log = structlog.get_logger(__name__)


class ExecutionPaused(Exception):
    """
    Raised by approval.wait (integrations/core/nodes.py) to pause a whole
    execution — not a node failure, a deliberate hold pending a human
    decision. Caught specifically in execute_workflow's result-handling
    loop, distinct from a generic node Exception (which fails the run).
    """
    def __init__(self, approval_id: str, node_id: str):
        self.approval_id = approval_id
        self.node_id = node_id
        super().__init__(f"Execution paused pending approval {approval_id} at node {node_id}")


# ─── Node dispatcher ──────────────────────────────────────────────────────────
# Maps node_type → async callable(node_config, input_data, credential_id, db)

NODE_HANDLERS: dict = {}

def register_node(node_type: str):
    """Decorator to register a node handler."""
    def decorator(fn):
        NODE_HANDLERS[node_type] = fn
        return fn
    return decorator


# ─── Topological sort ─────────────────────────────────────────────────────────

def topological_sort(nodes: list[dict], edges: list[dict]) -> list[list[str]]:
    """
    Returns execution levels: nodes in the same level can run in parallel.
    edges: [{"source": node_id, "target": node_id}]
    """
    in_degree: dict[str, int] = {n["id"]: 0 for n in nodes}
    adjacency: dict[str, list[str]] = defaultdict(list)

    for edge in edges:
        adjacency[edge["source"]].append(edge["target"])
        in_degree[edge["target"]] += 1

    queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
    levels: list[list[str]] = []

    while queue:
        level = list(queue)
        levels.append(level)
        next_queue = deque()
        for nid in level:
            for neighbor in adjacency[nid]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    next_queue.append(neighbor)
        queue = next_queue

    total = sum(len(l) for l in levels)
    if total != len(nodes):
        raise ValueError("Workflow graph has a cycle")

    return levels


# ─── Single node execution (with retry) ───────────────────────────────────────

async def _execute_node(
    node: dict,
    input_data: dict,
    db: AsyncSession,
    workflow_owner_id: str | None = None,
    workflow_id: str | None = None,
    execution_id: str | None = None,
) -> dict:
    node_type = node.get("type")
    handler = NODE_HANDLERS.get(node_type)
    if not handler:
        raise ValueError(f"No handler registered for node type: {node_type}")

    credential_id = node.get("credential_id")
    if credential_id:
        # Cross-tenant authorization check. Every integration handler
        # (Stripe, database, Slack, S3, all ~25 of them) trusts
        # credential_id at face value and just decrypts whatever it
        # points at — none of them independently verify the credential
        # actually belongs to the person who owns this workflow. Without
        # this check here, a workflow could reference ANY credential ID
        # in the whole database (guessed, leaked via a log, inherited
        # from a duplicated workflow after leaving an org, etc.) and the
        # engine would happily decrypt and use someone else's Stripe key,
        # database password, or Slack token on their behalf. This is the
        # single choke point every node execution passes through
        # regardless of integration, which is what makes it the right
        # place to enforce this — not inside 25 individual handler files,
        # where it's one line away from being forgotten in the 26th.
        from sqlalchemy import select as _select
        from storage.models import OAuthCredential as _OAuthCredential

        cred_owner_result = await db.execute(
            _select(_OAuthCredential.user_id).where(_OAuthCredential.id == credential_id)
        )
        cred_owner_id = cred_owner_result.scalar_one_or_none()
        if cred_owner_id is None:
            raise ValueError(f"Credential {credential_id} does not exist")
        if workflow_owner_id is None or cred_owner_id != workflow_owner_id:
            log.error(
                "credential_ownership_mismatch",
                credential_id=credential_id, credential_owner=cred_owner_id, workflow_owner=workflow_owner_id,
            )
            raise PermissionError(
                f"Node '{node.get('id')}' references a credential that does not belong to this workflow's owner. Refusing to run it."
            )

    max_attempts = node.get("retry", {}).get("max_attempts", 1)
    wait_min = node.get("retry", {}).get("wait_min", 1)
    wait_max = node.get("retry", {}).get("wait_max", 60)

    # A copy, not a mutation of node["config"] itself — several handlers
    # (ai.chat_with_memory, vector.*, approval.wait) need to know which
    # workflow/execution they're running inside of (to scope stored
    # memory/vectors/approvals), but that's engine context, not something
    # a user configures — leading underscore marks it as injected, and a
    # copy means retries/logging never see it leak into the node's own
    # persisted config.
    handler_config = {**node.get("config", {}), "_workflow_id": workflow_id, "_execution_id": execution_id, "_node_id": node.get("id")}

    for attempt in range(1, max_attempts + 1):
        try:
            result = await handler(
                config=handler_config,
                input_data=input_data,
                credential_id=credential_id,
                db=db,
            )
            return result
        except Exception as exc:
            if attempt == max_attempts:
                raise
            wait = min(wait_min * (2 ** (attempt - 1)), wait_max)
            log.warning("node_retry", node_id=node["id"], attempt=attempt, wait=wait)
            await asyncio.sleep(wait)


# ─── Full workflow execution ───────────────────────────────────────────────────

async def execute_workflow(
    execution_id: str,
    workflow_definition: dict,
    trigger_data: dict,
) -> None:
    """
    Main execution entry point. Called by Celery worker.
    """
    async with db_context() as db:
        from sqlalchemy import select, update
        from core.telemetry import trace_workflow_execution

        # Load execution row
        result = await db.execute(
            select(Execution).where(Execution.id == execution_id)
        )
        execution = result.scalar_one_or_none()
        if not execution:
            log.error("execution_not_found", execution_id=execution_id)
            return

        # Plan execution-limit safety net. workflows.py's manual_execute
        # already pre-checks this for the manual-trigger path so the
        # caller gets an immediate 402 instead of a queued execution that
        # silently fails — but webhook and scheduled triggers
        # (api/routes/webhooks.py, triggers/engine.py) create the
        # Execution row directly without an HTTP round-trip to reject,
        # so THIS is the check that actually catches those paths. Every
        # execution funnels through here regardless of trigger source,
        # which is what makes this the authoritative enforcement point.
        from sqlalchemy import select as _select
        from storage.models import Workflow as _Workflow
        from core.plans import check_execution_limit
        from fastapi import HTTPException as _HTTPException

        wf_result = await db.execute(_select(_Workflow.org_id, _Workflow.owner_id).where(_Workflow.id == execution.workflow_id))
        wf_row = wf_result.first()
        org_id, workflow_owner_id = wf_row if wf_row else (None, None)
        try:
            await check_execution_limit(org_id, db)
        except _HTTPException as e:
            execution.status = ExecutionStatus.failed
            execution.error = e.detail
            execution.finished_at = datetime.utcnow()
            await db.commit()
            log.info("execution_blocked_by_plan_limit", execution_id=execution_id, org_id=org_id)
            return

        with trace_workflow_execution(execution_id, execution.workflow_id):
            resuming = execution.status == ExecutionStatus.waiting
            execution.status = ExecutionStatus.running
            if not resuming:
                execution.started_at = datetime.utcnow()
            await db.flush()

            nodes_by_id: dict[str, dict] = {
                n["id"]: n for n in workflow_definition.get("nodes", [])
            }
            edges = workflow_definition.get("edges", [])
            # On resume, start from whatever was already completed — a
            # fresh `node_results = {}` would re-run every node from
            # scratch, which for anything with a side effect (an email
            # already sent, a Slack message already posted) is not just
            # wasted work, it's a real duplicate-action bug.
            node_results: dict[str, Any] = dict(execution.node_results or {}) if resuming else {}
            context: dict[str, Any] = {"trigger": trigger_data}

            # ── Policy / Guardrails check ────────────────────────────────
            try:
                from core.policy_engine import check_policies
                policy_result = await check_policies(
                    workflow_definition,
                    {"org_id": org_id, "trigger_data": trigger_data, "execution_id": execution_id},
                    db,
                )
                if not policy_result["passed"]:
                    execution.status = ExecutionStatus.failed
                    execution.error = "Policy violation: " + "; ".join(policy_result["violations"])
                    execution.finished_at = datetime.utcnow()
                    await db.commit()
                    log.info("execution_blocked_by_policy", execution_id=execution_id, violations=policy_result["violations"])
                    return
            except Exception as policy_exc:
                log.warning("policy_check_failed", execution_id=execution_id, error=str(policy_exc))

            try:
                from api.middleware.rbac import WRITE_CAPABLE_NODE_TYPES, user_has_permission
                from storage.models import User, Workflow as WorkflowModel

                if any(n.get("type") in WRITE_CAPABLE_NODE_TYPES for n in nodes_by_id.values()):
                    owner_result = await db.execute(
                        select(User)
                        .join(WorkflowModel, WorkflowModel.owner_id == User.id)
                        .where(WorkflowModel.id == execution.workflow_id)
                    )
                    owner = owner_result.scalar_one_or_none()
                    if owner and not user_has_permission(owner, "workflow:use_database_execute"):
                        raise PermissionError(
                            "This workflow contains a database write node (database.execute), but "
                            "the workflow owner's current role no longer permits it. An org "
                            "admin/owner needs to re-save the workflow or remove that node."
                        )

                levels = topological_sort(list(nodes_by_id.values()), edges)

                for level in levels:
                    # Build input for each node in this level
                    tasks = []
                    runnable_ids = []
                    for node_id in level:
                        if node_id in node_results and node_results[node_id].get("status") in ("success", "error"):
                            continue  # already ran before a pause — don't redo it on resume
                        node = nodes_by_id[node_id]
                        input_data = _build_node_input(node_id, edges, node_results, trigger_data)
                        tasks.append(_run_node_tracked(node, input_data, db, node_results, workflow_owner_id, execution.workflow_id, execution_id))
                        runnable_ids.append(node_id)

                    if not tasks:
                        continue

                    # Parallel execution within a level
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    paused: ExecutionPaused | None = None
                    for node_id, res in zip(runnable_ids, results):
                        if isinstance(res, ExecutionPaused):
                            node_results[node_id] = {"status": "waiting", "approval_id": res.approval_id}
                            paused = res
                        elif isinstance(res, Exception):
                            # node_results already populated by _run_node_tracked
                            if node_id not in node_results or not isinstance(node_results[node_id], dict) or node_results[node_id].get("status") != "error":
                                node_results[node_id] = {
                                    "status": "error",
                                    "error": str(res),
                                }
                            if nodes_by_id[node_id].get("required", True):
                                raise res
                        else:
                            # node_results already populated by _run_node_tracked with rich data
                            if node_id not in node_results or not isinstance(node_results.get(node_id), dict) or "output" not in node_results.get(node_id, {}):
                                node_results[node_id] = {"status": "success", "output": res}

                    if paused is not None:
                        execution.status = ExecutionStatus.waiting
                        execution.node_results = node_results
                        await db.commit()
                        log.info("execution_paused_for_approval", execution_id=execution_id, approval_id=paused.approval_id)
                        return

                execution.status = ExecutionStatus.success

            except Exception as exc:
                execution.status = ExecutionStatus.failed
                execution.error = traceback.format_exc()
                log.error("workflow_failed", execution_id=execution_id, error=str(exc))

            finally:
                execution.node_results = node_results
                execution.finished_at = datetime.utcnow()
                await db.commit()


async def _run_node_tracked(node: dict, input_data: dict, db: AsyncSession, node_results: dict, workflow_owner_id: str | None = None, workflow_id: str | None = None, execution_id: str | None = None):
    node_id = node["id"]
    started_at = datetime.utcnow()
    start = time.monotonic()
    retries = 0
    try:
        output = await _execute_node(node, input_data, db, workflow_owner_id, workflow_id, execution_id)
        duration_ms = int((time.monotonic() - start) * 1000)
        finished_at = datetime.utcnow()
        log.info("node_success", node_id=node_id, type=node.get("type"), duration_ms=duration_ms)
        # Store rich debug data in node_results
        node_results[node_id] = {
            "status": "success",
            "output": output,
            "input_data": input_data,
            "output_data": output,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_ms": duration_ms,
            "retries": retries,
            "error": None,
        }
        return output
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        finished_at = datetime.utcnow()
        if exc.__class__.__name__ == "ExecutionPaused":
            log.info("node_paused", node_id=node_id, type=node.get("type"), duration_ms=duration_ms)
        else:
            log.error("node_failed", node_id=node_id, type=node.get("type"),
                      duration_ms=duration_ms, error=str(exc))
            # Store failure debug data
            node_results[node_id] = {
                "status": "error",
                "error": str(exc),
                "error_traceback": traceback.format_exc(),
                "input_data": input_data,
                "output_data": None,
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "duration_ms": duration_ms,
                "retries": retries,
            }
        raise


def _build_node_input(node_id: str, edges: list[dict], node_results: dict, trigger_data: dict) -> dict:
    """Merge outputs of all parent nodes as input to this node."""
    parents = [e["source"] for e in edges if e["target"] == node_id]
    if not parents:
        return trigger_data

    merged = {}
    for parent_id in parents:
        if parent_id in node_results:
            result = node_results[parent_id]
            if isinstance(result, dict) and "output" in result:
                merged.update(result["output"] or {})
    return merged

async def resume_execution(execution_id: str, node_id: str, approval: dict) -> None:
    import json
    import redis.asyncio as aioredis
    from datetime import datetime
    from core.config import settings

    approval_key = f"approval:{execution_id}:{node_id}"
    r = aioredis.from_url(settings.REDIS_URL)
    try:
        payload = json.dumps({**approval, "approved_at": datetime.utcnow().isoformat()})
        await r.rpush(approval_key, payload)
        await r.expire(approval_key, 3600)
    finally:
        await r.aclose()


class ExecutionContext:
    pass
