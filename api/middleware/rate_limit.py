"""
Per-identity rate limiting.

nginx (nginx.conf) already rate-limits by IP at the edge, which stops raw
flood traffic but has two gaps at 1M-user scale:
  1. Many real users share an IP (corporate NAT, mobile carrier CGNAT) —
     an IP limit throttles all of them together for one person's traffic.
  2. A single abusive account can dodge an IP limit just by rotating
     source IPs / using a proxy pool.

This middleware limits by the authenticated user (JWT `sub` claim) when a
valid token is present, and falls back to IP only for anonymous requests
(login, signup, public webhook receivers). It's a fixed-window counter in
Redis — simpler than a sliding window / token bucket and good enough for
an abuse backstop; swap for a proper token bucket if you need smoother
burst handling later.

We only decode the JWT here, we never look the user up in the database —
that keeps this middleware cheap enough to run on every request without
adding a DB round-trip. Signature/expiry are still verified, so a forged
or expired token just falls back to the (stricter) anonymous IP limit.
"""
import time

import structlog
from fastapi import Request, Response
from jose import jwt, JWTError
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import settings

log = structlog.get_logger(__name__)

_redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)

# Requests per window, per identity.
AUTHENTICATED_LIMIT = 600
ANONYMOUS_LIMIT = 60
WINDOW_SECONDS = 60

_EXEMPT_PATH_PREFIXES = ("/health", "/metrics", "/api/docs", "/api/redoc", "/api/openapi.json", "/api/billing/webhook")


def _identity(request: Request) -> tuple[str, int]:
    """Returns (redis_key_identity, limit) for this request."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:]
        try:
            payload = jwt.decode(token, settings.APP_SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("sub")
            if user_id:
                return f"user:{user_id}", AUTHENTICATED_LIMIT
        except JWTError:
            pass  # falls through to IP-based anonymous limit

    ip = request.client.host if request.client else "unknown"
    return f"ip:{ip}", ANONYMOUS_LIMIT


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith(_EXEMPT_PATH_PREFIXES):
            return await call_next(request)

        identity, limit = _identity(request)
        window = int(time.time()) // WINDOW_SECONDS
        key = f"ratelimit:{identity}:{window}"

        try:
            count = await _redis.incr(key)
            if count == 1:
                await _redis.expire(key, WINDOW_SECONDS)
        except Exception:
            # Redis being down should degrade to "allow", not take the API
            # down with it — this is an abuse backstop, not a correctness
            # requirement.
            log.warning("rate_limit_redis_unavailable")
            return await call_next(request)

        if count > limit:
            log.info("rate_limit_exceeded", identity=identity, count=count, limit=limit)
            return Response(
                content='{"detail":"Rate limit exceeded. Please slow down."}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(WINDOW_SECONDS), "X-RateLimit-Limit": str(limit)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(limit - count, 0))
        return response
