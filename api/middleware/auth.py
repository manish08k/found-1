"""JWT authentication middleware."""
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.config import settings
from storage.database import get_db
from storage.models import User

ALGORITHM = "HS256"
# Short-lived on purpose: a stolen access token is only useful for 15
# minutes. Session continuity comes from the refresh token
# (create_refresh_token / rotate_refresh_token below), not from a
# long-lived access token.
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
bearer_scheme = HTTPBearer(auto_error=False)

# ── Redis-backed login rate limiter (per-IP) ─────────────────────────────────
# Shared across all API replicas/pods, survives restarts.
_redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
_LOGIN_MAX_ATTEMPTS = 10
_LOGIN_WINDOW_SECONDS = 60

# ── Per-account lockout ───────────────────────────────────────────────────────
# The per-IP limiter above stops a single source flooding logins; it does
# NOT stop a credential-stuffing attack that spreads attempts for the SAME
# account across many IPs/proxies. This locks the *account* after repeated
# failures regardless of source IP.
_ACCOUNT_LOCKOUT_MAX_ATTEMPTS = 5
_ACCOUNT_LOCKOUT_SECONDS = 15 * 60


async def check_login_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    key = f"login_attempts:{ip}"
    count = await _redis.incr(key)
    if count == 1:
        await _redis.expire(key, _LOGIN_WINDOW_SECONDS)
    if count > _LOGIN_MAX_ATTEMPTS:
        ttl = await _redis.ttl(key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please wait a minute.",
            headers={"Retry-After": str(max(ttl, 1))},
        )


async def reset_login_rate_limit(request: Request) -> None:
    """Call on successful login to clear the counter."""
    ip = request.client.host if request.client else "unknown"
    await _redis.delete(f"login_attempts:{ip}")


async def check_account_lockout(email: str) -> None:
    locked = await _redis.get(f"account_lock:{email}")
    if locked:
        ttl = await _redis.ttl(f"account_lock:{email}")
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="This account is temporarily locked due to repeated failed login attempts.",
            headers={"Retry-After": str(max(ttl, 1))},
        )


async def record_failed_login(email: str) -> None:
    key = f"account_failures:{email}"
    count = await _redis.incr(key)
    if count == 1:
        await _redis.expire(key, _ACCOUNT_LOCKOUT_SECONDS)
    if count >= _ACCOUNT_LOCKOUT_MAX_ATTEMPTS:
        await _redis.set(f"account_lock:{email}", "1", ex=_ACCOUNT_LOCKOUT_SECONDS)


async def reset_account_lockout(email: str) -> None:
    await _redis.delete(f"account_failures:{email}", f"account_lock:{email}")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: str, email: str, scope: str = "full", expire_minutes: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expire_minutes or ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user_id, "email": email, "exp": expire, "iat": now, "jti": str(uuid.uuid4()), "scope": scope}
    return jwt.encode(payload, settings.APP_SECRET_KEY, algorithm=ALGORITHM)


async def revoke_access_token(token: str) -> None:
    """Add a token's jti to a deny-list until its natural expiry (logout / suspected compromise)."""
    try:
        payload = jwt.decode(token, settings.APP_SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti and exp:
            ttl = max(int(exp - time.time()), 1)
            await _redis.set(f"revoked_jti:{jti}", "1", ex=ttl)
    except JWTError:
        pass


async def _is_revoked(jti: str | None) -> bool:
    if not jti:
        return False
    return bool(await _redis.get(f"revoked_jti:{jti}"))


async def _user_from_token(token: str, db: AsyncSession, required_scope: str | None = "full") -> User:
    try:
        payload = jwt.decode(token, settings.APP_SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise JWTError()
        if await _is_revoked(payload.get("jti")):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")
        # mfa_setup tokens are deliberately narrow-scope — issued mid-login
        # for a user who still needs to complete MFA enrollment, and must
        # NOT work as a general bearer token for every other endpoint.
        token_scope = payload.get("scope", "full")
        if required_scope and token_scope != required_scope:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token scope not permitted for this endpoint")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return await _user_from_token(credentials.credentials, db, required_scope="full")


async def get_current_user_mfa_setup(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """For /api/auth/mfa/* endpoints only, during the forced-enrollment step of login."""
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return await _user_from_token(credentials.credentials, db, required_scope="mfa_setup")


async def get_current_user_full_or_mfa_setup(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    MFA enroll/verify are reachable two ways: a normal logged-in user
    turning MFA on voluntarily from settings (full-scope token), or a
    user mid-login who's being forced to enroll because their role
    requires it (mfa_setup-scope token, which can't do anything else).
    """
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return await _user_from_token(credentials.credentials, db, required_scope=None)


async def get_current_user_flexible(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    oauth_token: Optional[str] = Cookie(default=None, alias="oauth_token"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Accepts JWT from Authorization header (primary) or a short-lived
    HttpOnly cookie named `oauth_token` (used only during the OAuth
    redirect dance — the cookie is set by /oauth/connect and consumed
    once the SPA reads it via /api/auth/me, then cleared).
    No longer accepts the token as a URL query parameter.
    """
    if credentials:
        return await _user_from_token(credentials.credentials, db)
    if oauth_token:
        return await _user_from_token(oauth_token, db)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
