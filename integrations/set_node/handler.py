"""
Set node — set or override field values in data.

No credentials required.

Config:
  - fields: list of {name, value, type} where type is one of:
      string, number, boolean, json

Takes input_data and sets/overrides the specified fields, returning the merged dict.
"""
import json as _json
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _coerce_value(value, type_hint: str):
    """Coerce a value to the requested type."""
    t = (type_hint or "string").lower().strip()
    if t == "string":
        return str(value) if value is not None else ""
    if t == "number":
        try:
            num = float(value)
            return int(num) if num == int(num) else num
        except (TypeError, ValueError):
            raise ValueError(f"Cannot convert {value!r} to number")
    if t == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")
        return bool(value)
    if t == "json":
        if isinstance(value, str):
            try:
                return _json.loads(value)
            except _json.JSONDecodeError as exc:
                raise ValueError(f"Cannot parse JSON value {value!r}: {exc}") from exc
        return value  # already a dict/list
    # Unknown type — pass through as-is
    return value


@register_node("set_node.set_fields")
async def set_node_set_fields(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Set or override fields in input_data.

    Config keys:
      fields : list[{name: str, value: any, type: str}]
               If not provided, falls back to input_data['fields'].
    """
    fields = config.get("fields") or input_data.get("fields", [])

    if not isinstance(fields, list):
        raise ValueError("set_node.set_fields: 'fields' must be a list of {name, value, type} objects")

    # Start with a copy of input_data so existing keys are preserved unless overridden
    result = dict(input_data)

    overrides: dict = {}
    for idx, field in enumerate(fields):
        if not isinstance(field, dict):
            raise ValueError(f"set_node.set_fields: field at index {idx} must be a dict, got {type(field)}")
        name = field.get("name")
        if not name:
            raise ValueError(f"set_node.set_fields: field at index {idx} missing 'name'")
        raw_value = field.get("value")
        type_hint = field.get("type", "string")
        coerced = _coerce_value(raw_value, type_hint)
        overrides[name] = coerced

    result.update(overrides)
    log.info("set_node.set_fields", fields_set=list(overrides.keys()))
    return result
