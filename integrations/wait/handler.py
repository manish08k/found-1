"""Wait integration — pause workflow execution for a duration or until a webhook fires."""
import asyncio
import uuid
from datetime import datetime, timezone

import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


@register_node("wait.wait")
async def wait_wait(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Pause workflow execution for a specified number of seconds.

    config/input_data:
      duration — seconds to sleep (default 1, max 3600)
    """
    merged = {**config, **input_data}
    duration = float(merged.get("duration", 1))
    duration = max(0, min(duration, 3600))  # clamp to [0, 3600]

    log.info("wait.wait", duration=duration)
    await asyncio.sleep(duration)

    resumed_at = datetime.now(timezone.utc).isoformat()
    return {
        "waited_seconds": duration,
        "resumed_at": resumed_at,
    }


@register_node("wait.wait_for_webhook")
async def wait_wait_for_webhook(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Register a temporary webhook URL for external callers to resume the workflow.

    Returns the webhook URL that must be called to continue workflow execution.
    The caller is responsible for polling or receiving the callback.

    config/input_data:
      (no required fields; optional timeout not enforced here)
    """
    webhook_id = str(uuid.uuid4())
    webhook_url = f"/webhook/wait/{webhook_id}"

    log.info("wait.wait_for_webhook", webhook_id=webhook_id, url=webhook_url)
    return {
        "webhook_id": webhook_id,
        "url": webhook_url,
    }
