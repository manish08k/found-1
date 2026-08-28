"""
Refresh token issuance + rotation.

Pairs with the short-lived (15 min) access token in api/middleware/auth.py.
A refresh token is:
  - stored as only a SHA-256 hash (never the raw token) — same principle
    as password hashing, so a DB leak alone doesn't hand out valid
    sessions.
  - single-use: every /api/auth/refresh call issues a NEW refresh token
    and marks the old one used (replaced_by_id) — this is "refresh token
    rotation".
  - reuse-detected: if an already-rotated (replaced_by_id is set) token
    is presented again, that's a strong signal the token was stolen and
    both the attacker and the legitimate user are now racing to use it.
    We respond by revoking the ENTIRE token chain for that user, forcing
    a fresh login everywhere.
"""
import hashlib
import secrets
from datetime import datetime, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from api.middleware.auth import REFRESH_TOKEN_EXPIRE_DAYS
from storage.models import RefreshToken

log = structlog.get_logger(__name__)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def create_refresh_token(
    db: AsyncSession, user_id: str, request=None,
) -> str:
    raw = secrets.token_urlsafe(48)
    row = RefreshToken(
        user_id=user_id,
        token_hash=_hash_token(raw),
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        user_agent=(request.headers.get("user-agent", "")[:512] if request else None),
        ip_address=(request.client.host if request and request.client else None),
    )
    db.add(row)
    await db.flush()
    return raw


async def rotate_refresh_token(db: AsyncSession, raw_token: str, request=None) -> tuple[str, str]:
    """
    Exchange a valid refresh token for a new (access_token_user_id, new_raw_refresh_token)
    pair. Raises ValueError on invalid/expired/revoked/reused tokens.
    """
    token_hash = _hash_token(raw_token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    row = result.scalar_one_or_none()

    if not row:
        raise ValueError("Invalid refresh token")

    if row.replaced_by_id is not None:
        # Reuse of an already-rotated token — treat as theft, nuke the
        # whole session chain for this user so both the legitimate holder
        # and whoever replayed this token are logged out.
        log.warning("refresh_token_reuse_detected", user_id=row.user_id, token_id=row.id)
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == row.user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.utcnow())
        )
        await db.flush()
        raise ValueError("Refresh token reuse detected — all sessions for this account have been revoked")

    if row.revoked_at is not None or row.expires_at < datetime.utcnow():
        raise ValueError("Refresh token expired or revoked")

    new_raw = secrets.token_urlsafe(48)
    new_row = RefreshToken(
        user_id=row.user_id,
        token_hash=_hash_token(new_raw),
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        user_agent=(request.headers.get("user-agent", "")[:512] if request else None),
        ip_address=(request.client.host if request and request.client else None),
    )
    db.add(new_row)
    await db.flush()

    row.replaced_by_id = new_row.id
    await db.flush()

    return row.user_id, new_raw


async def revoke_all_refresh_tokens(db: AsyncSession, user_id: str) -> None:
    """Call on password change / suspected compromise / explicit 'log out everywhere'."""
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.utcnow())
    )


async def revoke_refresh_token(db: AsyncSession, raw_token: str) -> None:
    """Call on logout — revoke just this one session, not every device."""
    token_hash = _hash_token(raw_token)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .values(revoked_at=datetime.utcnow())
    )
