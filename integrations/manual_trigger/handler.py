"""
ManualTrigger integration.

Provides a manually triggered workflow node that passes arbitrary input
data through with metadata (triggered_at, source, input_data).

No credentials required — pure passthrough with metadata enrichment.
"""
import structlog
from datetime import datetime, timezone

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


@register_node("manual_trigger.trigger")
async def manual_trigger_trigger(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Manually triggered workflow node.

    Passes through any input data with metadata fields:
      - triggered_at : ISO-8601 UTC timestamp
      - source       : always "manual"
      - input_data   : the original input_data payload
    """
    triggered_at = datetime.now(timezone.utc).isoformat()

    log.info("manual_trigger.trigger", triggered_at=triggered_at)

    return {
        "triggered_at": triggered_at,
        "source": "manual",
        "input_data": input_data,
    }
