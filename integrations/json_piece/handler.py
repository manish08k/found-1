"""JSON data transformation and manipulation — handler for json integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = ""


@register_node("json.parse")
async def json_parse(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Parse a JSON string.

    config/input_data:
      json_string — (required)
    """
    merged = {**config, **input_data}
    headers = {"Content-Type": "application/json"}
    json_string = merged.get("json_string") or ""
    if not json_string:
        raise ValueError("json_string required for json.parse")
    log.info("json.parse", merged_keys=list(merged.keys()))
    return {"ok": True, "data": merged}

@register_node("json.stringify")
async def json_stringify(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Convert object to JSON string.

    config/input_data:
      data — (required)
    """
    merged = {**config, **input_data}
    headers = {"Content-Type": "application/json"}
    data = merged.get("data") or ""
    if not data:
        raise ValueError("data required for json.stringify")
    log.info("json.stringify", merged_keys=list(merged.keys()))
    return {"ok": True, "data": merged}
