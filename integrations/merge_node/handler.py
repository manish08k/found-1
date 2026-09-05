"""
Merge node integration.

Provides pure data processing nodes to combine, join, or zip
data from multiple sources.

No credentials required — pure data processing.

Nodes:
  - merge_node.merge_by_key : SQL-style inner join on a shared key field
  - merge_node.combine      : Concatenate two lists into one
  - merge_node.zip          : Pair elements from two lists positionally
"""
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


@register_node("merge_node.merge_by_key")
async def merge_by_key(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Join two lists on a shared key field (SQL INNER JOIN semantics).

    Config / input fields:
      - list_a    : First list of dicts
      - list_b    : Second list of dicts
      - key       : Field name to join on (must exist in both lists)
      - join_type : "inner" (default) | "left" | "right"
    """
    list_a = config.get("list_a") or input_data.get("list_a", [])
    list_b = config.get("list_b") or input_data.get("list_b", [])
    key = config.get("key") or input_data.get("key")
    join_type = (config.get("join_type") or input_data.get("join_type", "inner")).lower()

    if not key:
        raise ValueError("merge_node.merge_by_key requires 'key'")
    if not isinstance(list_a, list):
        raise ValueError("merge_node.merge_by_key requires 'list_a' to be a list")
    if not isinstance(list_b, list):
        raise ValueError("merge_node.merge_by_key requires 'list_b' to be a list")

    # Build lookup from list_b keyed by join key
    b_by_key: dict = {}
    for item in list_b:
        k = item.get(key)
        if k is not None:
            b_by_key.setdefault(k, []).append(item)

    merged = []
    unmatched_a = []

    for item_a in list_a:
        k = item_a.get(key)
        matches = b_by_key.get(k, [])
        if matches:
            for item_b in matches:
                combined = {**item_b, **item_a}  # a wins on conflicts
                merged.append(combined)
        else:
            unmatched_a.append(item_a)

    result: dict = {"merged": merged, "count": len(merged)}

    if join_type == "left":
        result["merged"] = merged + unmatched_a
        result["count"] = len(result["merged"])
    elif join_type == "right":
        # All b items that had no a match
        matched_keys = {item_a.get(key) for item_a in list_a}
        unmatched_b = [item for item in list_b if item.get(key) not in matched_keys]
        result["merged"] = merged + unmatched_b
        result["count"] = len(result["merged"])

    log.info("merge_node.merge_by_key", key=key, join_type=join_type, output_count=result["count"])
    return result


@register_node("merge_node.combine")
async def merge_combine(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Concatenate two input lists into a single list.

    Config / input fields:
      - list_a : First list
      - list_b : Second list
    """
    list_a = config.get("list_a") or input_data.get("list_a", [])
    list_b = config.get("list_b") or input_data.get("list_b", [])

    if not isinstance(list_a, list):
        list_a = [list_a]
    if not isinstance(list_b, list):
        list_b = [list_b]

    combined = list_a + list_b
    log.info("merge_node.combine", a_count=len(list_a), b_count=len(list_b), total=len(combined))
    return {"combined": combined, "count": len(combined)}


@register_node("merge_node.zip")
async def merge_zip(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Zip two lists element-by-element into a list of merged dicts.

    Config / input fields:
      - list_a        : First list of dicts
      - list_b        : Second list of dicts
      - fill_missing  : bool — if True, pad shorter list with empty dicts (default False)
    """
    list_a = config.get("list_a") or input_data.get("list_a", [])
    list_b = config.get("list_b") or input_data.get("list_b", [])
    fill_missing = bool(config.get("fill_missing") or input_data.get("fill_missing", False))

    if not isinstance(list_a, list):
        list_a = [list_a]
    if not isinstance(list_b, list):
        list_b = [list_b]

    if fill_missing:
        max_len = max(len(list_a), len(list_b))
        list_a = list_a + [{}] * (max_len - len(list_a))
        list_b = list_b + [{}] * (max_len - len(list_b))

    zipped = []
    for a, b in zip(list_a, list_b):
        a_dict = a if isinstance(a, dict) else {"value_a": a}
        b_dict = b if isinstance(b, dict) else {"value_b": b}
        zipped.append({**b_dict, **a_dict})  # a wins on key conflicts

    log.info("merge_node.zip", output_count=len(zipped))
    return {"zipped": zipped, "count": len(zipped)}
