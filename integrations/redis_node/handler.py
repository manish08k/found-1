"""Redis integration — get, set, delete, list_keys, publish.

Credential fields:
  - host     : Redis hostname (default: localhost)
  - port     : Redis port (default: 6379)
  - password : Redis password (optional)
  - db       : Redis database index (default: 0)

Nodes:
  - redis_node.get        : retrieve a value by key
  - redis_node.set        : store a key/value pair
  - redis_node.delete     : remove one or more keys
  - redis_node.list_keys  : list keys matching a pattern
  - redis_node.publish    : publish a message to a channel
"""
import structlog
import httpx  # noqa: F401 — standard import

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Library import with fallback
# ---------------------------------------------------------------------------
try:
    import redis.asyncio as aioredis  # type: ignore
    _REDIS_BACKEND = "redis-py"
except ImportError:
    try:
        import aioredis  # type: ignore
        _REDIS_BACKEND = "aioredis"
    except ImportError:
        aioredis = None  # type: ignore
        _REDIS_BACKEND = None


def _require_redis():
    if aioredis is None:
        raise RuntimeError(
            "No Redis library found. Install one: pip install redis  # or aioredis"
        )


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

async def _get_redis(credential_id: str, db_session):
    """Build and return a redis client from stored credentials."""
    _require_redis()
    creds = await get_credential_data(credential_id, db_session)
    host = creds.get("host", "localhost")
    port = int(creds.get("port", 6379))
    password = creds.get("password") or None
    db_index = int(creds.get("db", 0))

    if _REDIS_BACKEND == "redis-py":
        import redis.asyncio as _r  # type: ignore
        client = _r.Redis(host=host, port=port, password=password, db=db_index,
                          decode_responses=True)
    else:
        import aioredis as _r  # type: ignore
        client = await _r.create_redis_pool(
            f"redis://{host}:{port}", password=password, db=db_index, encoding="utf-8"
        )
    return client


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@register_node("redis_node.get")
async def redis_get(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Get the value of a Redis key."""
    key = config.get("key") or input_data.get("key")
    if not key:
        raise ValueError("'key' is required")
    log.info("redis_node.get", key=key)
    client = await _get_redis(credential_id, db)
    try:
        value = await client.get(key)
    finally:
        await client.aclose() if hasattr(client, "aclose") else client.close()
    return {"key": key, "value": value, "exists": value is not None}


@register_node("redis_node.set")
async def redis_set(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Set a Redis key to a value, with optional TTL (seconds)."""
    key = config.get("key") or input_data.get("key")
    value = config.get("value") if config.get("value") is not None else input_data.get("value")
    ttl = config.get("ttl") or input_data.get("ttl")  # seconds, optional
    if not key:
        raise ValueError("'key' is required")
    if value is None:
        raise ValueError("'value' is required")
    # Coerce value to string for Redis storage
    value_str = str(value)
    log.info("redis_node.set", key=key, ttl=ttl)
    client = await _get_redis(credential_id, db)
    try:
        if ttl:
            result = await client.setex(key, int(ttl), value_str)
        else:
            result = await client.set(key, value_str)
    finally:
        await client.aclose() if hasattr(client, "aclose") else client.close()
    return {"key": key, "value": value_str, "ttl": ttl, "ok": bool(result)}


@register_node("redis_node.delete")
async def redis_delete(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Delete one or more Redis keys."""
    keys = config.get("keys") or input_data.get("keys")
    if not keys:
        # Fallback: single key
        key = config.get("key") or input_data.get("key")
        if not key:
            raise ValueError("'keys' (list) or 'key' is required")
        keys = [key]
    if isinstance(keys, str):
        keys = [keys]
    log.info("redis_node.delete", keys=keys)
    client = await _get_redis(credential_id, db)
    try:
        deleted = await client.delete(*keys)
    finally:
        await client.aclose() if hasattr(client, "aclose") else client.close()
    return {"keys": keys, "deleted_count": deleted}


@register_node("redis_node.list_keys")
async def redis_list_keys(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List Redis keys matching a pattern (default: *)."""
    pattern = config.get("pattern") or input_data.get("pattern", "*")
    count = int(config.get("count", 100))
    log.info("redis_node.list_keys", pattern=pattern, count=count)
    client = await _get_redis(credential_id, db)
    try:
        # Use SCAN to avoid blocking on large key spaces
        keys = []
        async for key in client.scan_iter(match=pattern, count=count):
            keys.append(key)
            if len(keys) >= count:
                break
    finally:
        await client.aclose() if hasattr(client, "aclose") else client.close()
    return {"pattern": pattern, "keys": keys, "count": len(keys)}


@register_node("redis_node.publish")
async def redis_publish(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Publish a message to a Redis Pub/Sub channel."""
    channel = config.get("channel") or input_data.get("channel")
    message = config.get("message") or input_data.get("message")
    if not channel:
        raise ValueError("'channel' is required")
    if message is None:
        raise ValueError("'message' is required")
    log.info("redis_node.publish", channel=channel)
    client = await _get_redis(credential_id, db)
    try:
        receivers = await client.publish(channel, str(message))
    finally:
        await client.aclose() if hasattr(client, "aclose") else client.close()
    return {"channel": channel, "message": str(message), "receivers": receivers}
