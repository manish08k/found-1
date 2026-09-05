"""
N8nTrainingCustomerDatastore integration.

A simple in-memory key-value store intended for training demos and
workflow examples. No external HTTP calls or credentials required.

The store is module-level and persists for the lifetime of the process.
All keys are stored as strings; values may be any JSON-serialisable type.
"""
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

# Module-level in-memory store
_STORE: dict[str, object] = {}


@register_node("n8n_training_datastore.set_value")
async def datastore_set_value(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Store a value under a given key."""
    key = config.get("key") or input_data.get("key")
    value = config.get("value") if "value" in config else input_data.get("value")

    if key is None:
        raise ValueError("n8n_training_datastore.set_value requires 'key'")
    if value is None:
        raise ValueError("n8n_training_datastore.set_value requires 'value'")

    key = str(key)
    _STORE[key] = value

    log.info("n8n_training_datastore.set_value", key=key)
    return {"key": key, "value": value, "stored": True}


@register_node("n8n_training_datastore.get_value")
async def datastore_get_value(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve a value by key. Returns None if the key does not exist."""
    key = config.get("key") or input_data.get("key")
    if key is None:
        raise ValueError("n8n_training_datastore.get_value requires 'key'")

    key = str(key)
    default = config.get("default") if "default" in config else input_data.get("default")
    value = _STORE.get(key, default)
    found = key in _STORE

    log.info("n8n_training_datastore.get_value", key=key, found=found)
    return {"key": key, "value": value, "found": found}


@register_node("n8n_training_datastore.delete_value")
async def datastore_delete_value(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Delete a key from the store. No-op if the key does not exist."""
    key = config.get("key") or input_data.get("key")
    if key is None:
        raise ValueError("n8n_training_datastore.delete_value requires 'key'")

    key = str(key)
    existed = key in _STORE
    _STORE.pop(key, None)

    log.info("n8n_training_datastore.delete_value", key=key, existed=existed)
    return {"key": key, "deleted": existed}


@register_node("n8n_training_datastore.list_keys")
async def datastore_list_keys(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all keys currently in the store."""
    prefix = config.get("prefix") or input_data.get("prefix", "")

    keys = sorted(k for k in _STORE.keys() if k.startswith(str(prefix)))

    log.info("n8n_training_datastore.list_keys", prefix=prefix, count=len(keys))
    return {"keys": keys, "count": len(keys)}
