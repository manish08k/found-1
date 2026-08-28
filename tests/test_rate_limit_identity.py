"""Tests for api/middleware/rate_limit.py's identity resolution logic."""
from types import SimpleNamespace

from jose import jwt

from core.config import settings
from api.middleware.rate_limit import _identity, AUTHENTICATED_LIMIT, ANONYMOUS_LIMIT


def _fake_request(auth_header: str | None, client_ip: str = "1.2.3.4"):
    headers = {"authorization": auth_header} if auth_header else {}
    return SimpleNamespace(
        headers=headers,
        client=SimpleNamespace(host=client_ip),
    )


def test_valid_token_uses_user_identity():
    token = jwt.encode({"sub": "user-123"}, settings.APP_SECRET_KEY, algorithm="HS256")
    identity, limit = _identity(_fake_request(f"Bearer {token}"))
    assert identity == "user:user-123"
    assert limit == AUTHENTICATED_LIMIT


def test_missing_auth_falls_back_to_ip():
    identity, limit = _identity(_fake_request(None, client_ip="9.9.9.9"))
    assert identity == "ip:9.9.9.9"
    assert limit == ANONYMOUS_LIMIT


def test_malformed_token_falls_back_to_ip():
    identity, limit = _identity(_fake_request("Bearer not-a-real-jwt", client_ip="5.5.5.5"))
    assert identity == "ip:5.5.5.5"
    assert limit == ANONYMOUS_LIMIT


def test_token_missing_sub_falls_back_to_ip():
    token = jwt.encode({"email": "x@example.com"}, settings.APP_SECRET_KEY, algorithm="HS256")
    identity, limit = _identity(_fake_request(f"Bearer {token}", client_ip="7.7.7.7"))
    assert identity == "ip:7.7.7.7"
    assert limit == ANONYMOUS_LIMIT
