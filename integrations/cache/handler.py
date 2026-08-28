"""
Cache nodes — store/retrieve LLM call results or arbitrary values.

Nodes:
  cache.in_memory       — module-level dict with optional TTL
  cache.redis           — Redis SET/GET with TTL
  cache.upstash_redis   — Upstash Redis REST API (no redis-py needed)
  cache.momento         — Momento serverless cache REST API
  cache.get             — retrieve a cached value by key
  cache.set             — store a value under a key
  cache.delete          — delete a key
  cache.clear           — clear all keys in a namespace
"""
import json
import time
from collections import defaultdict
from typing import Any

import httpx
import structlog

from core.config import settings
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

# ─── In-process store: {namespace: {key: (value, expires_at|None)}} ──────────
_STORE: dict[str, dict[str, tuple[Any, float | None]]] = defaultdict(dict)


def _in_memory_get(ns: str, key: str) -> Any | None:
    entry = _STORE[ns].get(key)
    if entry is None:
        return None
    value, exp = entry
    if exp is not None and time.time() > exp:
        del _STORE[ns][key]
        return None
    return value


def _in_memory_set(ns: str, key: str, value: Any, ttl: int | None) -> None:
    exp = time.time() + ttl if ttl else None
    _STORE[ns][key] = (value, exp)


def _in_memory_delete(ns: str, key: str) -> bool:
    return _STORE[ns].pop(key, None) is not None


# ─── cache.in_memory ─────────────────────────────────────────────────────────

@register_node("cache.in_memory")
async def cache_in_memory(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    In-process TTL cache. Operations: get | set | delete | clear.
    config: operation, namespace, key, value, ttl_seconds
    """
    operation = config.get("operation", "get").lower()
    namespace = config.get("namespace", "default")
    key = str(input_data.get("key") or config.get("key", ""))
    ttl = int(config.get("ttl_seconds", 0)) or None

    if operation == "get":
        val = _in_memory_get(namespace, key)
        return {"value": val, "hit": val is not None, "key": key}

    if operation == "set":
        value = input_data.get("value") if "value" in input_data else config.get("value")
        _in_memory_set(namespace, key, value, ttl)
        return {"stored": True, "key": key}

    if operation == "delete":
        removed = _in_memory_delete(namespace, key)
        return {"deleted": removed, "key": key}

    if operation == "clear":
        count = len(_STORE[namespace])
        _STORE[namespace].clear()
        return {"cleared": count, "namespace": namespace}

    return {"error": f"Unknown operation: {operation}"}


# ─── cache.redis ─────────────────────────────────────────────────────────────

@register_node("cache.redis")
async def cache_redis(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Redis cache using asyncio-native aioredis (redis-py async).
    config: operation, redis_url, key, value, ttl_seconds, namespace
    """
    try:
        import redis.asyncio as aioredis  # type: ignore
    except ImportError:
        raise ImportError("cache.redis requires redis package: pip install redis")

    operation = config.get("operation", "get").lower()
    redis_url = config.get("redis_url") or settings.REDIS_URL or "redis://localhost:6379/0"
    namespace = config.get("namespace", "autoflow")
    key_raw = str(input_data.get("key") or config.get("key", ""))
    full_key = f"{namespace}:{key_raw}" if namespace else key_raw
    ttl = int(config.get("ttl_seconds", 3600))

    client = aioredis.from_url(redis_url, decode_responses=True)
    try:
        if operation == "get":
            raw = await client.get(full_key)
            value = json.loads(raw) if raw is not None else None
            return {"value": value, "hit": raw is not None, "key": full_key}

        if operation == "set":
            value = input_data.get("value") if "value" in input_data else config.get("value")
            await client.setex(full_key, ttl, json.dumps(value, default=str))
            return {"stored": True, "key": full_key}

        if operation == "delete":
            deleted = await client.delete(full_key)
            return {"deleted": deleted > 0, "key": full_key}

        if operation == "clear":
            pattern = f"{namespace}:*"
            keys = await client.keys(pattern)
            if keys:
                deleted = await client.delete(*keys)
            else:
                deleted = 0
            return {"cleared": deleted, "namespace": namespace}

        return {"error": f"Unknown operation: {operation}"}
    finally:
        await client.aclose()


# ─── cache.upstash_redis ─────────────────────────────────────────────────────

@register_node("cache.upstash_redis")
async def cache_upstash_redis(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Upstash Redis via REST API — no redis-py needed.
    config: operation, upstash_url, upstash_token, key, value, ttl_seconds, namespace
    """
    operation = config.get("operation", "get").lower()
    upstash_url = config.get("upstash_url") or getattr(settings, "UPSTASH_REDIS_REST_URL", "")
    upstash_token = config.get("upstash_token") or getattr(settings, "UPSTASH_REDIS_REST_TOKEN", "")
    namespace = config.get("namespace", "autoflow")
    key_raw = str(input_data.get("key") or config.get("key", ""))
    full_key = f"{namespace}:{key_raw}" if namespace else key_raw
    ttl = int(config.get("ttl_seconds", 3600))

    if not upstash_url or not upstash_token:
        raise ValueError("cache.upstash_redis requires upstash_url and upstash_token")

    headers = {"Authorization": f"Bearer {upstash_token}"}

    async with httpx.AsyncClient(timeout=15) as c:
        if operation == "get":
            r = await c.get(f"{upstash_url}/get/{full_key}", headers=headers)
            r.raise_for_status()
            raw = r.json().get("result")
            value = json.loads(raw) if raw else None
            return {"value": value, "hit": raw is not None, "key": full_key}

        if operation == "set":
            value = input_data.get("value") if "value" in input_data else config.get("value")
            encoded = json.dumps(value, default=str)
            r = await c.get(f"{upstash_url}/setex/{full_key}/{ttl}/{encoded}", headers=headers)
            r.raise_for_status()
            return {"stored": True, "key": full_key}

        if operation == "delete":
            r = await c.get(f"{upstash_url}/del/{full_key}", headers=headers)
            r.raise_for_status()
            return {"deleted": r.json().get("result", 0) > 0, "key": full_key}

        if operation == "clear":
            r = await c.get(f"{upstash_url}/scan/0/match/{namespace}:*", headers=headers)
            r.raise_for_status()
            keys = r.json().get("result", [None, []])[1]
            deleted = 0
            for k in keys:
                await c.get(f"{upstash_url}/del/{k}", headers=headers)
                deleted += 1
            return {"cleared": deleted, "namespace": namespace}

    return {"error": f"Unknown operation: {operation}"}


# ─── cache.momento ───────────────────────────────────────────────────────────

@register_node("cache.momento")
async def cache_momento(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Momento serverless cache via REST API.
    config: operation, api_key, cache_name, key, value, ttl_seconds
    """
    operation = config.get("operation", "get").lower()
    api_key = config.get("api_key") or getattr(settings, "MOMENTO_API_KEY", "")
    cache_name = config.get("cache_name", "autoflow")
    key = str(input_data.get("key") or config.get("key", ""))
    ttl = int(config.get("ttl_seconds", 3600))

    if not api_key:
        raise ValueError("cache.momento requires a Momento API key")

    # Decode endpoint from API key (Momento JWT contains the endpoint)
    try:
        import base64
        payload_b64 = api_key.split(".")[1] + "=="
        payload = json.loads(base64.b64decode(payload_b64).decode())
        endpoint = payload.get("cp", "api.cache.cell-us-east-1-1.prod.a.momentohq.com")
    except Exception:
        endpoint = "api.cache.cell-us-east-1-1.prod.a.momentohq.com"

    base = f"https://{endpoint}/cache/{cache_name}"
    headers = {"Authorization": api_key}

    async with httpx.AsyncClient(timeout=15) as c:
        if operation == "get":
            r = await c.get(f"{base}?key={key}", headers=headers)
            if r.status_code == 404:
                return {"value": None, "hit": False, "key": key}
            r.raise_for_status()
            raw = r.content
            try:
                value = json.loads(raw)
            except Exception:
                value = raw.decode()
            return {"value": value, "hit": True, "key": key}

        if operation == "set":
            value = input_data.get("value") if "value" in input_data else config.get("value")
            encoded = json.dumps(value, default=str).encode()
            r = await c.put(f"{base}?key={key}&ttl_seconds={ttl}", headers=headers, content=encoded)
            r.raise_for_status()
            return {"stored": True, "key": key}

        if operation == "delete":
            r = await c.delete(f"{base}?key={key}", headers=headers)
            return {"deleted": r.status_code in (200, 204), "key": key}

    return {"error": f"Unknown operation: {operation}"}


# ─── cache.get / cache.set / cache.delete / cache.clear ──────────────────────
# Convenience nodes that always use in-memory for simple workflow use.

@register_node("cache.get")
async def cache_get(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    namespace = config.get("namespace", "default")
    key = str(input_data.get("key") or config.get("key", ""))
    value = _in_memory_get(namespace, key)
    return {"value": value, "hit": value is not None, "key": key}


@register_node("cache.set")
async def cache_set(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    namespace = config.get("namespace", "default")
    key = str(input_data.get("key") or config.get("key", ""))
    value = input_data.get("value") if "value" in input_data else config.get("value")
    ttl = int(config.get("ttl_seconds", 0)) or None
    _in_memory_set(namespace, key, value, ttl)
    return {"stored": True, "key": key}


@register_node("cache.delete")
async def cache_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    namespace = config.get("namespace", "default")
    key = str(input_data.get("key") or config.get("key", ""))
    removed = _in_memory_delete(namespace, key)
    return {"deleted": removed, "key": key}


@register_node("cache.clear")
async def cache_clear(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    namespace = config.get("namespace", "default")
    count = len(_STORE[namespace])
    _STORE[namespace].clear()
    return {"cleared": count, "namespace": namespace}
