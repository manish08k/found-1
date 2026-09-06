"""Flow Parser integration — parse and transform workflow data."""
import json
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


@register_node("flow_parser.parse_json")
async def flow_parser_parse_json(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    raw = merged.get("json_string", "{}")
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        return {"parsed": parsed, "success": True}
    except json.JSONDecodeError as e:
        return {"parsed": None, "success": False, "error": str(e)}


@register_node("flow_parser.extract_path")
async def flow_parser_extract_path(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    data = merged.get("data", {})
    path = merged.get("path", "").split(".")
    result = data
    for key in path:
        if isinstance(result, dict):
            result = result.get(key)
        else:
            result = None
            break
    return {"value": result, "path": ".".join(path)}
