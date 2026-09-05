"""RespondToWebhook integration — send a response back to a webhook caller.

No credentials required.

Nodes:
  - respond_to_webhook.respond : construct and return a webhook response payload

Config:
  - status_code : HTTP status code (default: 200)
  - body        : response body — dict or string (default: {})
  - headers     : dict of response headers (default: {})
"""
import structlog
import httpx  # noqa: F401 — standard import

from core.execution_engine import register_node
from oauth.flow import get_credential_data  # noqa: F401 — standard import

log = structlog.get_logger(__name__)


@register_node("respond_to_webhook.respond")
async def respond(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Return a structured webhook response payload."""
    status_code = int(config.get("status_code", input_data.get("status_code", 200)))
    body = config.get("body", input_data.get("body", {}))
    headers = config.get("headers", input_data.get("headers", {}))

    if not isinstance(headers, dict):
        raise ValueError("'headers' must be a dict")

    # Normalise body: if it's a dict, keep it; if string, wrap it
    if isinstance(body, dict):
        response_body = body
    else:
        response_body = {"message": str(body)}

    log.info(
        "respond_to_webhook.respond",
        status_code=status_code,
        headers=list(headers.keys()),
    )

    return {
        "responded": True,
        "status_code": status_code,
        "body": response_body,
        "headers": headers,
    }
