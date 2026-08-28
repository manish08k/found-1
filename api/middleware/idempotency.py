"""
Idempotency-Key support for endpoints that trigger side effects
(webhook receivers, manual workflow triggers) — so a client/webhook
sender retrying a request after a timeout doesn't cause the workflow to
run twice.

Contract: caller sends `Idempotency-Key: <uuid-or-any-unique-string>`.
  - First request with a given key: runs normally, response is cached.
  - Any later request with the SAME key (within TTL): the *cached*
    response is replayed immediately, the handler does NOT run again.
  - No key header: request proceeds normally, uncached (idempotency is
    opt-in — most GET/read endpoints don't need it and forcing a key on
    everything would break existing API clients).

Scope is deliberately narrow (path prefixes below) rather than global:
idempotency-by-default on every POST would silently cache things like
login (wrong — two logins from two devices shouldn't collide) unless
every route also namespaced keys by user, which is more invasive than
this feature needs to be right now.
"""
import hashlib
import json

import structlog
from fastapi import Request, Response
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import settings

log = structlog.get_logger(__name__)

_redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)

TTL_SECONDS = 24 * 60 * 60  # replay window for a given key

# Endpoints where a duplicate call has a real side effect worth guarding.
_IDEMPOTENT_PATH_PREFIXES = ("/webhooks/", "/api/triggers", "/api/executions")


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method not in ("POST", "PUT", "PATCH"):
            return await call_next(request)
        if not request.url.path.startswith(_IDEMPOTENT_PATH_PREFIXES):
            return await call_next(request)

        idem_key = request.headers.get("idempotency-key")
        if not idem_key:
            return await call_next(request)

        # Namespace by path too, so the same key reused across two
        # different endpoints (client bug) doesn't cross-contaminate.
        cache_key = f"idempotency:{request.url.path}:{idem_key}"

        try:
            cached = await _redis.get(cache_key)
        except Exception:
            log.warning("idempotency_redis_unavailable")
            return await call_next(request)

        if cached:
            data = json.loads(cached)
            log.info("idempotency_replay", path=request.url.path, key=idem_key)
            return Response(
                content=data["body"],
                status_code=data["status_code"],
                media_type=data.get("media_type", "application/json"),
                headers={"Idempotency-Replayed": "true"},
            )

        # First time we've seen this key — try to claim it atomically so
        # two concurrent retries of the same request don't both execute.
        try:
            claimed = await _redis.set(f"{cache_key}:lock", "1", nx=True, ex=30)
        except Exception:
            claimed = True  # Redis unavailable — degrade to "allow through"

        if not claimed:
            return Response(
                content='{"detail":"A request with this Idempotency-Key is already in progress."}',
                status_code=409,
                media_type="application/json",
            )

        response = await call_next(request)

        # Buffer the body so we can cache it, then rebuild the response —
        # BaseHTTPMiddleware response bodies are single-use async iterators.
        body_chunks = [section async for section in response.body_iterator]
        body = b"".join(body_chunks)

        if 200 <= response.status_code < 300:
            try:
                await _redis.set(
                    cache_key,
                    json.dumps({
                        "status_code": response.status_code,
                        "body": body.decode("utf-8", errors="replace"),
                        "media_type": response.media_type,
                    }),
                    ex=TTL_SECONDS,
                )
            except Exception:
                log.warning("idempotency_cache_write_failed")

        return Response(
            content=body,
            status_code=response.status_code,
            media_type=response.media_type,
            headers=dict(response.headers),
        )
