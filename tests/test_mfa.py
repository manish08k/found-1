"""Tests for api/middleware/mfa.py."""
from types import SimpleNamespace

import pyotp
import pytest

from api.middleware.mfa import (
    generate_mfa_secret, encrypt_mfa_secret, decrypt_mfa_secret,
    verify_totp_code, mfa_required_for,
)


def test_secret_roundtrip_through_encryption():
    secret = generate_mfa_secret()
    blob = encrypt_mfa_secret(secret)
    assert decrypt_mfa_secret(blob) == secret


def test_verify_totp_code_accepts_current_code():
    secret = generate_mfa_secret()
    code = pyotp.TOTP(secret).now()
    assert verify_totp_code(secret, code) is True


def test_verify_totp_code_rejects_wrong_code():
    secret = generate_mfa_secret()
    assert verify_totp_code(secret, "000000") is False


def _user(role, org_id="org-1"):
    role_obj = SimpleNamespace(value=role) if role else None
    return SimpleNamespace(org_id=org_id, role=role_obj)


@pytest.mark.parametrize("role,expected", [
    ("owner", True), ("admin", True), ("editor", False), ("viewer", False),
])
def test_mfa_required_for_elevated_roles_only(role, expected):
    assert mfa_required_for(_user(role)) is expected


def test_mfa_not_required_for_solo_user():
    assert mfa_required_for(_user(role=None, org_id=None)) is False
