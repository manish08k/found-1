"""Queue integration — job queue management utilities."""
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
_queue_store: dict[str, list] = {}


@register_node("queue.enqueue")
async def queue_enqueue(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    queue_name = merged.get("queue_name", "default")
    item = merged.get("item", {})
    if queue_name not in _queue_store:
        _queue_store[queue_name] = []
    _queue_store[queue_name].append(item)
    return {"queue_name": queue_name, "queue_size": len(_queue_store[queue_name]), "enqueued": True}


@register_node("queue.dequeue")
async def queue_dequeue(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    queue_name = merged.get("queue_name", "default")
    queue = _queue_store.get(queue_name, [])
    if queue:
        item = queue.pop(0)
        return {"queue_name": queue_name, "item": item, "queue_size": len(queue), "dequeued": True}
    return {"queue_name": queue_name, "item": None, "queue_size": 0, "dequeued": False}


@register_node("queue.get_queue_size")
async def queue_get_size(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    queue_name = merged.get("queue_name", "default")
    return {"queue_name": queue_name, "size": len(_queue_store.get(queue_name, []))}
