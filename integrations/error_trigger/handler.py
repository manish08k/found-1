"""
ErrorTrigger integration — structured workflow error handling.

Captures error context from a failed workflow execution and returns a
normalised error payload that can be routed to notification or logging nodes.

No credentials or HTTP calls are required.
"""
import datetime
import structlog
import httpx  # noqa: F401 – kept for platform consistency

from core.execution_engine import register_node
from oauth.flow import get_credential_data  # noqa: F401 – kept for platform consistency

log = structlog.get_logger(__name__)


@register_node("error_trigger.on_error")
async def on_error(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Capture and normalise error information from a failed workflow node.

    This node is typically placed at the start of an error-handling branch.
    It reads error context either from config or from input_data (which the
    platform populates automatically on error paths).

    Config / input keys:
      - workflow_id   (str) : ID of the workflow that failed.
      - error_message (str) : Human-readable error description.
      - node_name     (str) : Name / ID of the node that raised the error.
      - execution_id  (str) : Platform execution ID.
      - severity      (str) : "error" | "warning" | "critical". Default "error".
      - extra         (dict): Any additional context to include.

    Returns:
      {
        "workflow_id"   : str,
        "error_message" : str,
        "timestamp"     : str  (ISO-8601 UTC),
        "node_name"     : str,
        "execution_id"  : str,
        "severity"      : str,
        "extra"         : dict
      }
    """
    workflow_id = (
        config.get("workflow_id")
        or input_data.get("workflow_id")
        or input_data.get("workflowId", "unknown")
    )
    error_message = (
        config.get("error_message")
        or input_data.get("error_message")
        or input_data.get("errorMessage")
        or input_data.get("error", {}).get("message", "An unknown error occurred")
        if isinstance(input_data.get("error"), dict)
        else input_data.get("error_message", "An unknown error occurred")
    )
    node_name = (
        config.get("node_name")
        or input_data.get("node_name")
        or input_data.get("nodeName", "unknown")
    )
    execution_id = (
        config.get("execution_id")
        or input_data.get("execution_id")
        or input_data.get("executionId", "")
    )
    severity = (
        config.get("severity")
        or input_data.get("severity", "error")
    ).lower()

    if severity not in ("error", "warning", "critical"):
        severity = "error"

    extra = config.get("extra") or input_data.get("extra", {})
    if not isinstance(extra, dict):
        extra = {"raw": extra}

    timestamp = datetime.datetime.utcnow().isoformat() + "Z"

    log.error(
        "error_trigger.on_error",
        workflow_id=workflow_id,
        node_name=node_name,
        error_message=error_message,
        severity=severity,
        execution_id=execution_id,
    )

    return {
        "workflow_id": workflow_id,
        "error_message": error_message,
        "timestamp": timestamp,
        "node_name": node_name,
        "execution_id": execution_id,
        "severity": severity,
        "extra": extra,
    }


@register_node("error_trigger.format_alert")
async def format_alert(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Format an error payload into a human-readable alert message.

    Useful for piping into Slack, email, or PagerDuty nodes.

    Config / input keys:
      - workflow_id   (str)
      - error_message (str)
      - node_name     (str)
      - timestamp     (str)
      - severity      (str)
      - template      (str): Optional Jinja-style template with {placeholders}.
                             Default: "[{severity}] Workflow {workflow_id} failed
                             at node {node_name}: {error_message} ({timestamp})"

    Returns:
      { "alert_message": str, "subject": str, "severity": str }
    """
    workflow_id = config.get("workflow_id") or input_data.get("workflow_id", "unknown")
    error_message = config.get("error_message") or input_data.get("error_message", "Unknown error")
    node_name = config.get("node_name") or input_data.get("node_name", "unknown")
    timestamp = config.get("timestamp") or input_data.get("timestamp", datetime.datetime.utcnow().isoformat() + "Z")
    severity = (config.get("severity") or input_data.get("severity", "error")).upper()
    template = (
        config.get("template")
        or input_data.get("template")
        or "[{severity}] Workflow {workflow_id} failed at node {node_name}: {error_message} ({timestamp})"
    )

    context = {
        "severity": severity,
        "workflow_id": workflow_id,
        "error_message": error_message,
        "node_name": node_name,
        "timestamp": timestamp,
    }

    try:
        alert_message = template.format(**context)
    except KeyError as e:
        alert_message = f"[{severity}] Workflow {workflow_id} error: {error_message}"
        log.warning("error_trigger.format_alert: template key missing", missing_key=str(e))

    subject = f"[{severity}] Workflow failure: {workflow_id}"

    return {
        "alert_message": alert_message,
        "subject": subject,
        "severity": severity.lower(),
    }
