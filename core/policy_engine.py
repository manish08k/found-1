"""
Policy Engine — enforces organizational guardrails on workflow executions.

Rule types:
  - node_allowlist: Only specified node types may be used
  - node_denylist: Block specified node types
  - credential_restriction: Only specified credential IDs allowed
  - keyword_block: Block keywords in input/output
  - require_approval: Require human approval for certain node types
  - rate_limit: Cap executions per hour
"""
from datetime import datetime, timedelta

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from storage.models import Policy, Execution

log = structlog.get_logger(__name__)


async def check_policies(
    workflow: dict,
    execution_context: dict,
    db: AsyncSession,
) -> dict:
    """
    Check all active policies for the org against the workflow/execution.

    Args:
        workflow: The workflow dict (with 'nodes', 'edges', 'org_id')
        execution_context: Context dict with 'org_id', 'trigger_data', 'execution_id'
        db: Database session

    Returns:
        {"passed": bool, "violations": [...], "required_approvals": [...], "warnings": [...]}
    """
    org_id = execution_context.get("org_id") or workflow.get("org_id")
    if not org_id:
        return {"passed": True, "violations": [], "required_approvals": [], "warnings": []}

    # Load active policies for org
    result = await db.execute(
        select(Policy).where(
            Policy.org_id == org_id,
            Policy.is_active == True,
        )
    )
    policies = result.scalars().all()

    if not policies:
        return {"passed": True, "violations": [], "required_approvals": [], "warnings": []}

    violations = []
    required_approvals = []
    warnings = []

    nodes = workflow.get("nodes", []) if isinstance(workflow, dict) else []
    node_types = [n.get("type", "") for n in nodes]
    trigger_data = execution_context.get("trigger_data", {})

    for policy in policies:
        rules = policy.rules or []

        for rule in rules:
            rule_type = rule.get("type", "")
            rule_config = rule.get("config", {})

            if rule_type == "node_allowlist":
                allowed = set(rule_config.get("allowed_node_types", []))
                if allowed:
                    for nt in node_types:
                        if nt not in allowed:
                            msg = f"Policy '{policy.name}': node type '{nt}' is not in the allowlist"
                            if policy.action == "block":
                                violations.append(msg)
                            elif policy.action == "warn":
                                warnings.append(msg)
                            elif policy.action == "require_approval":
                                required_approvals.append(msg)

            elif rule_type == "node_denylist":
                denied = set(rule_config.get("denied_node_types", []))
                for nt in node_types:
                    if nt in denied:
                        msg = f"Policy '{policy.name}': node type '{nt}' is blocked"
                        if policy.action == "block":
                            violations.append(msg)
                        elif policy.action == "warn":
                            warnings.append(msg)
                        elif policy.action == "require_approval":
                            required_approvals.append(msg)

            elif rule_type == "credential_restriction":
                allowed_creds = set(rule_config.get("credential_ids", []))
                if allowed_creds:
                    for node in nodes:
                        cred_id = node.get("credential_id")
                        if cred_id and cred_id not in allowed_creds:
                            msg = f"Policy '{policy.name}': credential '{cred_id}' not in allowed list"
                            if policy.action == "block":
                                violations.append(msg)
                            else:
                                warnings.append(msg)

            elif rule_type == "keyword_block":
                keywords = rule_config.get("keywords", [])
                apply_to = rule_config.get("apply_to", "both")
                text_to_check = ""

                if apply_to in ("input", "both"):
                    import json
                    text_to_check += json.dumps(trigger_data).lower()

                for kw in keywords:
                    if kw.lower() in text_to_check:
                        msg = f"Policy '{policy.name}': blocked keyword '{kw}' found in input"
                        if policy.action == "block":
                            violations.append(msg)
                        elif policy.action == "warn":
                            warnings.append(msg)

            elif rule_type == "require_approval":
                approval_types = set(rule_config.get("node_types", []))
                for nt in node_types:
                    if nt in approval_types:
                        required_approvals.append(
                            f"Policy '{policy.name}': node type '{nt}' requires approval"
                        )

            elif rule_type == "rate_limit":
                max_per_hour = rule_config.get("max_executions_per_hour", 0)
                if max_per_hour > 0:
                    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
                    count_result = await db.execute(
                        select(func.count(Execution.id)).where(
                            Execution.created_at >= one_hour_ago
                        )
                    )
                    recent_count = count_result.scalar_one()
                    if recent_count >= max_per_hour:
                        msg = (
                            f"Policy '{policy.name}': rate limit exceeded "
                            f"({recent_count}/{max_per_hour} executions in last hour)"
                        )
                        if policy.action == "block":
                            violations.append(msg)
                        else:
                            warnings.append(msg)

    passed = len(violations) == 0
    return {
        "passed": passed,
        "violations": violations,
        "required_approvals": required_approvals,
        "warnings": warnings,
    }
