"""
Compare Datasets integration.

Pure data-processing node — no credentials or HTTP calls required.
Compares two lists of records by a key field and returns three buckets:
items only in A, items only in B, and items present in both.
"""
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


@register_node("compare_datasets.compare")
async def compare_datasets(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Compare two datasets by a key field.

    Config / input_data:
      - input_a : List of dicts (dataset A, required)
      - input_b : List of dicts (dataset B, required)
      - key     : Field name to compare records by (required)
      - include_values : If True (default), include full record objects in results;
                         if False, include only the key values.

    Returns:
      - only_in_a : Records whose key value exists only in A
      - only_in_b : Records whose key value exists only in B
      - in_both   : Records whose key value appears in both datasets
                    (each element is {"a": <record from A>, "b": <record from B>})
      - summary   : Counts for each bucket
    """
    input_a = config.get("input_a") or input_data.get("input_a")
    input_b = config.get("input_b") or input_data.get("input_b")
    key = config.get("key") or input_data.get("key")
    include_values = bool(config.get("include_values", True))

    if input_a is None:
        raise ValueError("compare_datasets.compare requires 'input_a'")
    if input_b is None:
        raise ValueError("compare_datasets.compare requires 'input_b'")
    if not key:
        raise ValueError("compare_datasets.compare requires 'key'")

    if not isinstance(input_a, list):
        raise TypeError(f"'input_a' must be a list, got {type(input_a).__name__}")
    if not isinstance(input_b, list):
        raise TypeError(f"'input_b' must be a list, got {type(input_b).__name__}")

    # Build lookup maps: key_value -> record
    def _build_index(dataset: list, key_field: str) -> dict:
        index: dict = {}
        for i, record in enumerate(dataset):
            if not isinstance(record, dict):
                raise TypeError(
                    f"All items in dataset must be dicts; item at index {i} is {type(record).__name__}"
                )
            if key_field not in record:
                log.warning(
                    "compare_datasets: record missing key field",
                    index=i,
                    key=key_field,
                )
                continue
            k = record[key_field]
            # Use string representation as dict key to handle various types
            index[str(k)] = record
        return index

    index_a = _build_index(input_a, key)
    index_b = _build_index(input_b, key)

    keys_a = set(index_a.keys())
    keys_b = set(index_b.keys())

    only_a_keys = keys_a - keys_b
    only_b_keys = keys_b - keys_a
    both_keys = keys_a & keys_b

    if include_values:
        only_in_a = [index_a[k] for k in sorted(only_a_keys)]
        only_in_b = [index_b[k] for k in sorted(only_b_keys)]
        in_both = [
            {"a": index_a[k], "b": index_b[k]}
            for k in sorted(both_keys)
        ]
    else:
        only_in_a = sorted(only_a_keys)
        only_in_b = sorted(only_b_keys)
        in_both = sorted(both_keys)

    result = {
        "only_in_a": only_in_a,
        "only_in_b": only_in_b,
        "in_both": in_both,
        "summary": {
            "only_in_a_count": len(only_in_a),
            "only_in_b_count": len(only_in_b),
            "in_both_count": len(in_both),
            "total_a": len(input_a),
            "total_b": len(input_b),
            "key": key,
        },
    }

    log.info(
        "compare_datasets completed",
        only_in_a=len(only_in_a),
        only_in_b=len(only_in_b),
        in_both=len(in_both),
    )
    return result
