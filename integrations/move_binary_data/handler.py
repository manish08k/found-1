"""
MoveBinaryData integration.

Pure data-transformation nodes for moving, copying, and deleting binary data
fields within the workflow item. No external HTTP calls or credentials required.
"""
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


@register_node("move_binary_data.move")
async def move_binary_data_move(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Move binary data from one field to another, removing the source field."""
    source_field = config.get("source_field") or input_data.get("source_field")
    destination_field = config.get("destination_field") or input_data.get("destination_field")

    if not source_field:
        raise ValueError("move_binary_data.move requires 'source_field'")
    if not destination_field:
        raise ValueError("move_binary_data.move requires 'destination_field'")

    binary_data = input_data.get(source_field)
    if binary_data is None:
        raise ValueError(f"move_binary_data.move: source field '{source_field}' not found in input_data")

    log.info("move_binary_data.move", source=source_field, destination=destination_field)

    result = dict(input_data)
    result[destination_field] = binary_data
    del result[source_field]
    return result


@register_node("move_binary_data.copy")
async def move_binary_data_copy(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Copy binary data from one field to another, keeping the source field."""
    source_field = config.get("source_field") or input_data.get("source_field")
    destination_field = config.get("destination_field") or input_data.get("destination_field")

    if not source_field:
        raise ValueError("move_binary_data.copy requires 'source_field'")
    if not destination_field:
        raise ValueError("move_binary_data.copy requires 'destination_field'")

    binary_data = input_data.get(source_field)
    if binary_data is None:
        raise ValueError(f"move_binary_data.copy: source field '{source_field}' not found in input_data")

    log.info("move_binary_data.copy", source=source_field, destination=destination_field)

    result = dict(input_data)
    result[destination_field] = binary_data
    return result


@register_node("move_binary_data.delete_field")
async def move_binary_data_delete_field(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Delete a binary data field from the workflow item."""
    field = config.get("field") or input_data.get("field")

    if not field:
        raise ValueError("move_binary_data.delete_field requires 'field'")

    if field not in input_data:
        log.warning("move_binary_data.delete_field: field not present, skipping", field=field)
        return dict(input_data)

    log.info("move_binary_data.delete_field", field=field)

    result = dict(input_data)
    del result[field]
    return result
