"""Tests for WebhookDispatcher signature validation."""
import hashlib
import hmac
import pytest
from fastapi import HTTPException

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from triggers.engine import WebhookDispatcher


def _sig(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_valid_signature_passes():
    body = b'{"event": "push"}'
    secret = "mysecret"
    headers = {"x-hub-signature-256": _sig(body, secret)}
    WebhookDispatcher._validate_signature(body, secret, headers)  # no exception


def test_invalid_signature_raises_401():
    body = b'{"event": "push"}'
    headers = {"x-hub-signature-256": "sha256=deadbeef"}
    with pytest.raises(HTTPException) as exc_info:
        WebhookDispatcher._validate_signature(body, "mysecret", headers)
    assert exc_info.value.status_code == 401


def test_missing_signature_raises_401():
    body = b'{"event": "push"}'
    with pytest.raises(HTTPException) as exc_info:
        WebhookDispatcher._validate_signature(body, "mysecret", {})
    assert exc_info.value.status_code == 401


def test_autoflow_signature_header_accepted():
    body = b"hello"
    secret = "s3cr3t"
    headers = {"x-autoflow-signature": _sig(body, secret)}
    WebhookDispatcher._validate_signature(body, secret, headers)


def test_tampered_body_raises():
    body = b'{"event": "push"}'
    secret = "mysecret"
    sig = _sig(body, secret)
    tampered = b'{"event": "malicious"}'
    with pytest.raises(HTTPException):
        WebhookDispatcher._validate_signature(tampered, secret, {"x-hub-signature-256": sig})
