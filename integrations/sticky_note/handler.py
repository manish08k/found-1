"""StickyNote integration — workflow annotation node (no HTTP, no credentials)."""
from datetime import datetime, timezone

import structlog
import httpx  # noqa: F401 — standard import kept for consistency

from core.execution_engine import register_node
from oauth.flow import get_credential_data  # noqa: F401 — standard import

log = structlog.get_logger(__name__)


@register_node("sticky_note.create")
async def sticky_note_create(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Annotation-only node. Stores a coloured note alongside the workflow canvas.
    No HTTP calls are made; no credentials are required.
    """
    content = config.get("content") or input_data.get("content", "")
    color = config.get("color") or input_data.get("color", "#FFD700")

    # Validate hex color format loosely
    if not isinstance(color, str) or not color.startswith("#"):
        color = "#FFD700"

    created_at = datetime.now(timezone.utc).isoformat()

    log.info("sticky_note.create", color=color, content_length=len(content))

    return {
        "content": content,
        "color": color,
        "created_at": created_at,
    }
