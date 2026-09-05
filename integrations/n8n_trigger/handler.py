"""
N8n Trigger integration — respond to n8n workflow events via webhook.

No credentials required; event payload is forwarded from input_data.

Nodes:
  - n8n_trigger.on_workflow_event  config: event_type, workflow_id
"""
import structlog
import httpx  # noqa: F401 — kept for platform consistency

from core.execution_engine import register_node
from oauth.flow import get_credential_data  # noqa: F401 — kept for platform consistency

log = structlog.get_logger(__name__)

_VALID_EVENT_TYPES = {"workflow.started", "workflow.completed", "workflow.failed"}


@register_node("n8n_trigger.on_workflow_event")
async def on_workflow_event(
    config: dict, input_data: dict, credential_id: str, db
) -> dict:
    """
    Respond to an n8n workflow lifecycle event delivered via webhook.

    Config:
      event_type  — one of: workflow.started | workflow.completed | workflow.failed
      workflow_id — (optional) only process events for this workflow ID
    """
    event_type = config.get("event_type") or input_data.get("event_type")
    workflow_id = config.get("workflow_id") or input_data.get("workflow_id")

    if event_type and event_type not in _VALID_EVENT_TYPES:
        raise ValueError(
            f"n8n_trigger: unknown event_type '{event_type}'. "
            f"Must be one of: {', '.join(sorted(_VALID_EVENT_TYPES))}"
        )

    received_event = input_data.get("event_type") or input_data.get("type")
    received_workflow = input_data.get("workflow_id") or input_data.get("workflowId")

    log.info(
        "n8n_trigger.on_workflow_event received",
        event_type=received_event,
        workflow_id=received_workflow,
        filter_event_type=event_type,
        filter_workflow_id=workflow_id,
    )

    # If filters are set, check they match
    if event_type and received_event and received_event != event_type:
        log.debug(
            "n8n_trigger: event_type mismatch, skipping",
            expected=event_type,
            got=received_event,
        )
        return {"__skipped__": True, "reason": "event_type_mismatch", **input_data}

    if workflow_id and received_workflow and str(received_workflow) != str(workflow_id):
        log.debug(
            "n8n_trigger: workflow_id mismatch, skipping",
            expected=workflow_id,
            got=received_workflow,
        )
        return {"__skipped__": True, "reason": "workflow_id_mismatch", **input_data}

    return dict(input_data)
