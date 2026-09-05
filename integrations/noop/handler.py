"""
NoOp — pass-through node that does nothing.

No credentials required.

Nodes:
  - noop.pass_through — returns input_data unchanged with {__noop__: true} merged in
"""
import structlog
import httpx  # noqa: F401 — kept for platform consistency

from core.execution_engine import register_node
from oauth.flow import get_credential_data  # noqa: F401 — kept for platform consistency

log = structlog.get_logger(__name__)


@register_node("noop.pass_through")
async def pass_through(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Return input_data unchanged, with ``__noop__: true`` added.

    Useful as a placeholder, debugging aid, or conditional branch no-op.
    """
    log.debug("noop.pass_through", keys=list(input_data.keys()))
    return {**input_data, "__noop__": True}
