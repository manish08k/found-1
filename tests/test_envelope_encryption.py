"""Tests for credentials/envelope.py — envelope encryption for credentials."""
import pytest

from credentials.envelope import encrypt_credential_envelope, decrypt_credential_envelope
from credentials.encryption import encrypt_credential
from core.config import settings


def test_roundtrip():
    data = {"host": "db.internal", "password": "hunter2"}
    blob = encrypt_credential_envelope(data, org_id="org-A")
    assert decrypt_credential_envelope(blob, org_id="org-A") == data


def test_wrong_org_id_fails_closed():
    blob = encrypt_credential_envelope({"x": 1}, org_id="org-A")
    with pytest.raises(ValueError):
        decrypt_credential_envelope(blob, org_id="org-B")


def test_none_org_id_is_its_own_context():
    blob = encrypt_credential_envelope({"x": 1}, org_id=None)
    assert decrypt_credential_envelope(blob, org_id=None) == {"x": 1}
    with pytest.raises(ValueError):
        decrypt_credential_envelope(blob, org_id="some-org")


def test_same_plaintext_different_ciphertext():
    """Each credential gets its own random DEK — not a shared key."""
    data = {"password": "hunter2"}
    blob1 = encrypt_credential_envelope(data, org_id="org-A")
    blob2 = encrypt_credential_envelope(data, org_id="org-A")
    assert blob1 != blob2
    assert decrypt_credential_envelope(blob1, org_id="org-A") == data
    assert decrypt_credential_envelope(blob2, org_id="org-A") == data


def test_legacy_flat_blob_still_decrypts():
    """Backward compatibility: pre-envelope rows must keep working."""
    data = {"password": "legacy"}
    legacy_blob = encrypt_credential(data, settings.CREDENTIAL_ENCRYPTION_KEY)
    assert decrypt_credential_envelope(legacy_blob, org_id=None) == data


def test_envelope_blob_is_versioned_json():
    import json
    blob = encrypt_credential_envelope({"a": 1}, org_id="org-A")
    envelope = json.loads(blob)
    assert envelope["v"] == 2
    assert envelope["org_id"] == "org-A"
    assert "wrapped_dek" in envelope and "nonce" in envelope and "ciphertext" in envelope
