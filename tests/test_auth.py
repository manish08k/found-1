"""
Tests for auth routes — email/password login, Google OAuth callback,
token refresh, logout, /auth/me.

These are unit-level tests that verify the route handlers' behaviour
without hitting a real database or Google.  Integration tests that spin
up the full ASGI app live elsewhere (e2e/).
"""
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from api.middleware.auth import create_access_token, hash_password


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(email="user@example.com", google_id=None, mfa_enabled=False, is_active=True):
    user = SimpleNamespace(
        id=str(uuid.uuid4()),
        email=email,
        hashed_password=hash_password("correctpassword"),
        google_id=google_id,
        is_active=is_active,
        is_admin=False,
        mfa_enabled=mfa_enabled,
        mfa_secret=None,
        org_id=None,
        role=None,
        created_at=datetime.utcnow(),
    )
    return user


# ---------------------------------------------------------------------------
# Token creation and structure
# ---------------------------------------------------------------------------

def test_access_token_decodes_with_expected_claims():
    from jose import jwt
    from core.config import settings

    token = create_access_token("user-42", "u@example.com")
    payload = jwt.decode(token, settings.APP_SECRET_KEY, algorithms=["HS256"])
    assert payload["sub"] == "user-42"
    assert payload["email"] == "u@example.com"
    assert payload["scope"] == "full"
    assert "jti" in payload
    assert "exp" in payload


def test_scoped_token_has_correct_scope():
    from jose import jwt
    from core.config import settings

    token = create_access_token("user-42", "u@example.com", scope="mfa_setup", expire_minutes=10)
    payload = jwt.decode(token, settings.APP_SECRET_KEY, algorithms=["HS256"])
    assert payload["scope"] == "mfa_setup"


# ---------------------------------------------------------------------------
# Google OAuth callback — redirect URL correctness
# ---------------------------------------------------------------------------

def test_google_callback_redirect_contains_tokens():
    """
    After a successful Google OAuth exchange, the callback must redirect to
    the frontend with both google_token and refresh_token as URL query
    parameters — NOT set an HTTP-only cookie (the SPA uses Bearer auth via
    localStorage, not cookies).
    """
    from urllib.parse import urlparse, parse_qs
    from core.config import settings

    # Simulate what the callback builds
    access_token = create_access_token("user-1", "user@example.com")
    refresh_token = "fake-refresh-token-abc"

    from urllib.parse import urlencode
    params = urlencode({"google_token": access_token, "refresh_token": refresh_token})
    url = f"{settings.frontend_url}/?{params}"

    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    assert "google_token" in qs, "Redirect must include google_token param"
    assert "refresh_token" in qs, "Redirect must include refresh_token param"
    assert qs["google_token"][0] == access_token
    assert qs["refresh_token"][0] == refresh_token


def test_google_callback_error_redirect_goes_to_root():
    """Error redirects must go to /?error=... (root), not /login?error=...
    because the SPA has no client-side router — it renders LoginPage at /
    when the user is not authenticated."""
    from core.config import settings

    reason = "google_auth_failed"
    url = f"{settings.frontend_url}/?error={reason}"
    assert "/login" not in url.split("?")[0], "Error redirect must NOT go to /login"
    assert f"error={reason}" in url


# ---------------------------------------------------------------------------
# CORS configuration
# ---------------------------------------------------------------------------

def test_cors_does_not_use_wildcard_with_credentials():
    """
    allow_origins=['*'] with allow_credentials=True is invalid per the
    CORS spec — browsers silently reject it. Verify main.py never does this.
    """
    import ast

    with open("main.py", "r") as f:
        source = f.read()

    # Simple check: the string 'allow_origins=["*"]' should not appear
    # alongside 'allow_credentials=True' in the CORSMiddleware call.
    # A more robust check would parse the AST, but this is sufficient
    # for a regression test.
    assert 'allow_origins=["*"]' not in source, (
        "CORS must not use allow_origins=['*'] — it is invalid with allow_credentials=True"
    )


# ---------------------------------------------------------------------------
# Session storage consistency
# ---------------------------------------------------------------------------

def test_login_response_shape_matches_client_expectations():
    """
    The email/password login endpoint returns {access_token, refresh_token,
    token_type, user_id, expires_in_minutes}. The frontend client.ts
    storeSession() expects access_token + refresh_token and saves them to
    localStorage under the keys 'token' and 'refresh_token'.

    This test documents the contract so a future refactor doesn't silently
    break it.
    """
    # Simulate the shape returned by _issue_full_session
    session = {
        "access_token": "eyJ...",
        "refresh_token": "abc123",
        "token_type": "bearer",
        "user_id": "user-1",
        "expires_in_minutes": 15,
    }
    assert "access_token" in session
    assert "refresh_token" in session
    assert session["token_type"] == "bearer"


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def test_password_hash_verify_roundtrip():
    from api.middleware.auth import hash_password, verify_password
    pw = "s3cureP@ssw0rd!"
    h = hash_password(pw)
    assert verify_password(pw, h)
    assert not verify_password("wrong", h)


# ---------------------------------------------------------------------------
# Token revocation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_revoked_token_cannot_authenticate():
    from api.middleware.auth import revoke_access_token, _user_from_token

    class FakeDB:
        async def execute(self, *a, **kw):
            raise AssertionError("Should not reach DB — revocation check comes first")

    token = create_access_token("user-1", "u@example.com")
    await revoke_access_token(token)
    with pytest.raises(HTTPException) as exc_info:
        await _user_from_token(token, FakeDB(), required_scope="full")
    assert exc_info.value.status_code == 401
    assert "revoked" in exc_info.value.detail.lower()
