"""
ItemLists — work with lists of items.

Utility nodes for common list operations: splitting, aggregating,
deduplication, and sorting.

No credentials required.

Nodes:
  - item_lists.split_out          : explode a list field into individual items
  - item_lists.aggregate          : collect items from a repeated field into a list
  - item_lists.remove_duplicates  : deduplicate a list by a key field
  - item_lists.sort               : sort a list by a field (asc or desc)
"""
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _get_nested(obj: dict, key: str):
    """Support dot-notation keys like 'user.email'."""
    parts = key.split(".")
    current = obj
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


@register_node("item_lists.split_out")
async def item_lists_split_out(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Explode a list field into individual item records.

    Config / input_data fields:
      - field_name  (required) : the key in input_data whose value is a list
      - include_parent_fields  : if True, each output item includes the
                                 non-list fields from input_data (default True)

    Returns:
      { "items": [ {field_name: value, ...parent_fields} ], "count": int }
    """
    field_name = config.get("field_name") or input_data.get("field_name")
    if not field_name:
        raise ValueError("item_lists.split_out requires 'field_name'")

    include_parent = bool(
        config.get("include_parent_fields", True)
        if "include_parent_fields" in config
        else input_data.get("include_parent_fields", True)
    )

    raw_list = input_data.get(field_name)
    if raw_list is None:
        raise ValueError(f"item_lists.split_out: field '{field_name}' not found in input_data")
    if not isinstance(raw_list, list):
        raw_list = [raw_list]

    parent_fields = {k: v for k, v in input_data.items() if k != field_name} if include_parent else {}

    items = []
    for element in raw_list:
        if isinstance(element, dict):
            item = {**parent_fields, **element}
        else:
            item = {**parent_fields, field_name: element}
        items.append(item)

    log.info("item_lists.split_out", field=field_name, count=len(items))
    return {"items": items, "count": len(items)}


@register_node("item_lists.aggregate")
async def item_lists_aggregate(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Collect items from a repeated field into a single list.

    Config / input_data fields:
      - field_name (required) : key to extract from each element in 'items'
      - items                 : list of dicts to aggregate (defaults to
                                input_data.get('items'))
      - output_key            : name for the aggregated list in the output
                                (default: value of field_name)

    Returns:
      { "<output_key>": [...], "count": int }
    """
    field_name = config.get("field_name") or input_data.get("field_name")
    if not field_name:
        raise ValueError("item_lists.aggregate requires 'field_name'")

    items = config.get("items") or input_data.get("items", [])
    output_key = config.get("output_key") or input_data.get("output_key", field_name)

    if not isinstance(items, list):
        raise ValueError("item_lists.aggregate: 'items' must be a list")

    aggregated = []
    for element in items:
        if isinstance(element, dict):
            val = _get_nested(element, field_name)
            if val is not None:
                aggregated.append(val)
        else:
            aggregated.append(element)

    log.info("item_lists.aggregate", field=field_name, count=len(aggregated))
    return {output_key: aggregated, "count": len(aggregated)}


@register_node("item_lists.remove_duplicates")
async def item_lists_remove_duplicates(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Remove duplicate items from a list, based on a key field.

    Config / input_data fields:
      - field_name (required) : the key field to use for uniqueness check
      - items                 : list of dicts (defaults to input_data.get('items'))
      - keep                  : 'first' (default) or 'last'

    Returns:
      { "items": [...], "count": int, "removed": int }
    """
    field_name = config.get("field_name") or input_data.get("field_name")
    if not field_name:
        raise ValueError("item_lists.remove_duplicates requires 'field_name'")

    items = config.get("items") or input_data.get("items", [])
    keep = (config.get("keep") or input_data.get("keep", "first")).lower()

    if not isinstance(items, list):
        raise ValueError("item_lists.remove_duplicates: 'items' must be a list")

    if keep == "last":
        items = list(reversed(items))

    seen: set = set()
    deduped: list = []
    for item in items:
        key_val = _get_nested(item, field_name) if isinstance(item, dict) else item
        key_str = str(key_val)
        if key_str not in seen:
            seen.add(key_str)
            deduped.append(item)

    if keep == "last":
        deduped = list(reversed(deduped))

    removed = len(items) - len(deduped)
    log.info("item_lists.remove_duplicates", field=field_name, removed=removed, remaining=len(deduped))
    return {"items": deduped, "count": len(deduped), "removed": removed}


@register_node("item_lists.sort")
async def item_lists_sort(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Sort a list of items by a specified field.

    Config / input_data fields:
      - field_name (required) : the key field to sort by (supports dot-notation)
      - items                 : list of dicts (defaults to input_data.get('items'))
      - order                 : 'ascending' (default) or 'descending'
      - type                  : 'auto' (default), 'string', or 'number'

    Returns:
      { "items": [...], "count": int }
    """
    field_name = config.get("field_name") or input_data.get("field_name")
    if not field_name:
        raise ValueError("item_lists.sort requires 'field_name'")

    items = config.get("items") or input_data.get("items", [])
    order = (config.get("order") or input_data.get("order", "ascending")).lower()
    sort_type = (config.get("type") or input_data.get("type", "auto")).lower()

    if not isinstance(items, list):
        raise ValueError("item_lists.sort: 'items' must be a list")

    reverse = order in ("descending", "desc")

    def sort_key(item):
        val = _get_nested(item, field_name) if isinstance(item, dict) else item
        if val is None:
            # None sorts last regardless of direction
            return (1, "", 0)
        if sort_type == "number":
            try:
                return (0, "", float(val))
            except (ValueError, TypeError):
                return (0, str(val), 0)
        if sort_type == "string":
            return (0, str(val).lower(), 0)
        # auto — try numeric first
        try:
            return (0, "", float(val))
        except (ValueError, TypeError):
            return (0, str(val).lower(), 0)

    sorted_items = sorted(items, key=sort_key, reverse=reverse)
    log.info("item_lists.sort", field=field_name, order=order, count=len(sorted_items))
    return {"items": sorted_items, "count": len(sorted_items)}
