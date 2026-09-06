"""Flow Helper integration — workflow utility nodes."""
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


@register_node("flow_helper.merge_data")
async def flow_helper_merge_data(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    data_a = merged.get("data_a", {})
    data_b = merged.get("data_b", {})
    return {"merged": {**data_a, **data_b}}


@register_node("flow_helper.filter_list")
async def flow_helper_filter_list(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    items = merged.get("items", [])
    field = merged.get("field", "")
    value = merged.get("value")
    filtered = [i for i in items if isinstance(i, dict) and i.get(field) == value]
    return {"items": filtered, "count": len(filtered)}


@register_node("flow_helper.map_list")
async def flow_helper_map_list(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    items = merged.get("items", [])
    field = merged.get("field", "")
    return {"values": [i.get(field) for i in items if isinstance(i, dict)]}
