"""Webhook integration — process incoming webhook payloads and build responses."""
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


@register_node("webhook.trigger")
async def webhook_trigger(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Process an incoming webhook payload.

    Acts as a passthrough: extracts the body from input_data and returns it
    as the node output for downstream processing.

    config:
      response_mode — "onReceived" or "lastNode" (default "onReceived")
      response_code — HTTP status code to send back (default 200)
      response_data — optional static response data to return immediately

    input_data:
      body    — request body (if present, used as the payload)
      headers — incoming request headers (preserved in output)
      query   — query string parameters (preserved in output)
      (any other fields are passed through as-is)
    """
    response_mode = config.get("response_mode", "onReceived")
    response_code = int(config.get("response_code", 200))
    response_data = config.get("response_data")

    # Extract body if nested under "body" key, otherwise use input_data directly
    if "body" in input_data:
        payload = input_data["body"]
    else:
        payload = input_data

    log.info(
        "webhook.trigger",
        response_mode=response_mode,
        response_code=response_code,
        has_body="body" in input_data,
    )
    return {
        "body": payload,
        "headers": input_data.get("headers", {}),
        "query": input_data.get("query", {}),
        "response_mode": response_mode,
        "response_code": response_code,
        "response_data": response_data,
    }


@register_node("webhook.respond")
async def webhook_respond(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Build a structured webhook response.

    config/input_data:
      response_code    — HTTP status code (default 200)
      response_data    — body to include in the response (default {})
      response_headers — dict of headers to set on the response (default {})
    """
    merged = {**config, **input_data}
    response_code = int(merged.get("response_code", 200))
    response_data = merged.get("response_data", {})
    response_headers = merged.get("response_headers", {})

    log.info("webhook.respond", status=response_code)
    return {
        "status": response_code,
        "body": response_data,
        "headers": response_headers,
    }
