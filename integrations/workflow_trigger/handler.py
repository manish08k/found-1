"""WorkflowTrigger integration — trigger and respond in sub-workflow scenarios."""
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


@register_node("workflow_trigger.trigger")
async def workflow_trigger_trigger(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Process an incoming workflow trigger payload.

    Merges config metadata with the incoming input_data and marks the trigger
    as fired. This node is used as the entry point for manually triggered
    sub-workflows in n8n-style pipelines.

    config:
      workflow_id — optional identifier for the triggered workflow
    """
    merged = {**config, **input_data}
    workflow_id = merged.get("workflow_id")

    result = {
        "triggered": True,
        "payload": input_data,
        "workflow_id": workflow_id,
        "source": "workflow_trigger",
    }

    log.info("workflow_trigger.trigger", workflow_id=workflow_id)
    return result


@register_node("workflow_trigger.respond")
async def workflow_trigger_respond(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a response back to the calling workflow.

    config:
      response_data — explicit response payload; falls back to input_data if absent
    """
    response_data = config.get("response_data") or input_data

    result = {
        "response": response_data,
        "status": "ok",
    }

    log.info("workflow_trigger.respond")
    return result
