"""
Filter node — filter items from a list based on a field/operator/value condition.

No external API calls; no credentials required.

Config fields:
  - field    : dot-notation field name within each item to test
  - operator : one of equals, not_equals, contains, not_contains,
               greater_than, less_than, is_empty, is_not_empty
  - value    : comparison value (omit for is_empty / is_not_empty)

Input:
  - input_data.items : list of dicts to filter

Output:
  - items : filtered list
  - count : number of items that passed the filter
  - total : total number of input items
"""
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _get_nested(item: dict, field: str):
    """Retrieve a nested value from a dict using dot notation."""
    parts = field.split(".")
    value = item
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def _matches(item: dict, field: str, operator: str, compare_value) -> bool:
    """Return True if item satisfies the filter condition."""
    actual = _get_nested(item, field)

    if operator == "is_empty":
        return actual is None or actual == "" or actual == [] or actual == {}

    if operator == "is_not_empty":
        return not (actual is None or actual == "" or actual == [] or actual == {})

    if operator == "equals":
        # Try numeric comparison when both sides look numeric
        try:
            return float(actual) == float(compare_value)
        except (TypeError, ValueError):
            return str(actual) == str(compare_value)

    if operator == "not_equals":
        try:
            return float(actual) != float(compare_value)
        except (TypeError, ValueError):
            return str(actual) != str(compare_value)

    if operator == "contains":
        if actual is None:
            return False
        return str(compare_value).lower() in str(actual).lower()

    if operator == "not_contains":
        if actual is None:
            return True
        return str(compare_value).lower() not in str(actual).lower()

    if operator == "greater_than":
        try:
            return float(actual) > float(compare_value)
        except (TypeError, ValueError):
            return str(actual) > str(compare_value)

    if operator == "less_than":
        try:
            return float(actual) < float(compare_value)
        except (TypeError, ValueError):
            return str(actual) < str(compare_value)

    if operator == "greater_than_or_equal":
        try:
            return float(actual) >= float(compare_value)
        except (TypeError, ValueError):
            return str(actual) >= str(compare_value)

    if operator == "less_than_or_equal":
        try:
            return float(actual) <= float(compare_value)
        except (TypeError, ValueError):
            return str(actual) <= str(compare_value)

    if operator == "starts_with":
        if actual is None:
            return False
        return str(actual).lower().startswith(str(compare_value).lower())

    if operator == "ends_with":
        if actual is None:
            return False
        return str(actual).lower().endswith(str(compare_value).lower())

    raise ValueError(
        f"Unknown filter operator '{operator}'. Supported: equals, not_equals, "
        "contains, not_contains, greater_than, less_than, greater_than_or_equal, "
        "less_than_or_equal, starts_with, ends_with, is_empty, is_not_empty"
    )


@register_node("filter.filter_items")
async def filter_items(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Filter a list of items using a configurable field/operator/value condition.

    Supports multiple conditions via 'conditions' list (all must match by default)
    or single condition via top-level 'field', 'operator', 'value'.
    """
    items = input_data.get("items", [])
    if not isinstance(items, list):
        raise ValueError("'input_data.items' must be a list of dicts")

    total = len(items)

    # Support either a single condition or multiple conditions
    conditions = config.get("conditions")
    if not conditions:
        field = config.get("field") or input_data.get("field")
        operator = config.get("operator") or input_data.get("operator", "equals")
        value = config.get("value") if "value" in config else input_data.get("value")

        if not field and operator not in ("is_empty", "is_not_empty"):
            raise ValueError("'field' is required in config")

        conditions = [{"field": field, "operator": operator, "value": value}]

    match_mode = config.get("match_mode", "all")  # "all" (AND) or "any" (OR)

    log.info(
        "filter.filter_items",
        conditions=conditions,
        match_mode=match_mode,
        total=total,
    )

    filtered = []
    for item in items:
        if not isinstance(item, dict):
            # Non-dict items fail all field-based filters
            continue

        results = [
            _matches(item, cond["field"], cond["operator"], cond.get("value"))
            for cond in conditions
        ]

        if match_mode == "any":
            passed = any(results)
        else:
            passed = all(results)

        if passed:
            filtered.append(item)

    log.info(
        "filter.filter_items.done",
        passed=len(filtered),
        rejected=total - len(filtered),
    )
    return {"items": filtered, "count": len(filtered), "total": total}
