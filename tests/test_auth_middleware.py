"""
Tests for auth middleware — rate limiter, account lockout, token creation,
scoped tokens, and revocation.

Pre-existing note: this file used to test an in-memory `_login_attempts`
dict that no longer exists — the real implementation (api/middleware/auth.py)
is Redis-backed and async, matching how it's actually used in
api/routes/auth.py. Rewritten to match reality rather than an internal
detail that was removed.
"""
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.middleware.auth import (
    check_login_rate_limit, reset_login_rate_limit,
    check_account_lockout, record_failed_login, reset_account_lockout,
    hash_password, verify_password,
    create_access_token, revoke_access_token, _user_from_token,
    _redis,
)


def _make_request(ip="1.2.3.4"):
    req = SimpleNamespace(client=SimpleNamespace(host=ip))
    return req


# ── Per-IP login rate limiter (Redis-backed) ─────────────────────────────────

@pytest.mark.asyncio
async def test_rate_limit_allows_under_threshold():
    ip = f"10.0.{uuid.uuid4().int % 255}.1"
    req = _make_request(ip)
    for _ in range(10):
        await check_login_rate_limit(req)  # should not raise


@pytest.mark.asyncio
async def test_rate_limit_blocks_over_threshold():
    ip = f"10.0.{uuid.uuid4().int % 255}.2"
    req = _make_request(ip)
    for _ in range(10):
        await check_login_rate_limit(req)
    with pytest.raises(HTTPException) as exc_info:
        await check_login_rate_limit(req)
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_rate_limit_reset_clears_counter():
    ip = f"10.0.{uuid.uuid4().int % 255}.3"
    req = _make_request(ip)
    for _ in range(10):
        await check_login_rate_limit(req)
    await reset_login_rate_limit(req)
    await check_login_rate_limit(req)  # should not raise after reset


@pytest.mark.asyncio
async def test_rate_limit_per_ip():
    ip_a = f"10.0.{uuid.uuid4().int % 255}.10"
    ip_b = f"10.0.{uuid.uuid4().int % 255}.11"
    for _ in range(10):
        await check_login_rate_limit(_make_request(ip_a))
    await check_login_rate_limit(_make_request(ip_b))  # different IP, should not raise


# ── Per-account lockout (independent of source IP) ──────────────────────────

@pytest.mark.asyncio
async def test_account_lockout_after_repeated_failures():
    email = f"lockout-{uuid.uuid4().hex[:8]}@example.com"
    await check_account_lockout(email)  # not locked yet
    for _ in range(5):
        await record_failed_login(email)
    with pytest.raises(HTTPException) as exc_info:
        await check_account_lockout(email)
    assert exc_info.value.status_code == 423


@pytest.mark.asyncio
async def test_account_lockout_reset_clears_it():
    email = f"lockout-{uuid.uuid4().hex[:8]}@example.com"
    for _ in range(5):
        await record_failed_login(email)
    await reset_account_lockout(email)
    await check_account_lockout(email)  # should not raise


# ── Password hashing ─────────────────────────────────────────────────────────

def test_hash_and_verify_password():
    pw = "correct-horse-battery-staple"
    hashed = hash_password(pw)
    assert verify_password(pw, hashed)
    assert not verify_password("wrong", hashed)


# ── Token creation, scope enforcement, revocation ────────────────────────────

def test_create_access_token_is_string():
    token = create_access_token("user-123", "user@example.com")
    assert isinstance(token, str)
    assert len(token) > 0


@pytest.mark.asyncio
async def test_scoped_token_rejected_outside_its_scope():
    """An mfa_setup-scope token must not pass as a full-scope token."""
    class FakeDB:
        async def execute(self, *a, **kw):
            raise AssertionError("should never reach the DB — scope check happens first")

    token = create_access_token("user-123", "user@example.com", scope="mfa_setup")
    with pytest.raises(HTTPException) as exc_info:
        await _user_from_token(token, FakeDB(), required_scope="full")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_revoked_token_is_rejected():
    class FakeDB:
        async def execute(self, *a, **kw):
            raise AssertionError("should never reach the DB — revocation check happens first")

    token = create_access_token("user-123", "user@example.com")
    await revoke_access_token(token)
    with pytest.raises(HTTPException) as exc_info:
        await _user_from_token(token, FakeDB(), required_scope="full")
    assert exc_info.value.status_code == 401
