"""
SplitInBatches node — split large lists into smaller batches.

No credentials required.

Config:
  batch_size (int): Number of items per batch (default 10).

Input:
  items (list): The list to split.

Returns:
  batches     (list[list]): The split batches.
  total_items (int)       : Total number of input items.
  batch_count (int)       : Number of batches produced.
"""
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


@register_node("split_in_batches.split")
async def split_in_batches_split(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Split an input list into fixed-size batches.

    Config keys:
      batch_size (int): Items per batch (default 10, min 1).

    Input keys:
      items (list): The list to batch.
    """
    batch_size = int(config.get("batch_size") or input_data.get("batch_size", 10))
    if batch_size < 1:
        raise ValueError("split_in_batches.split: 'batch_size' must be >= 1")

    items = config.get("items") or input_data.get("items", [])
    if not isinstance(items, list):
        raise ValueError("split_in_batches.split: 'items' must be a list")

    batches = [items[i : i + batch_size] for i in range(0, len(items), batch_size)]

    log.info(
        "split_in_batches.split",
        total_items=len(items),
        batch_size=batch_size,
        batch_count=len(batches),
    )
    return {
        "batches": batches,
        "total_items": len(items),
        "batch_count": len(batches),
    }
