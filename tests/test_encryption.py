"""Tests for credential encryption."""
import pytest
from credentials.encryption import encrypt_credential, decrypt_credential


SAMPLE_KEY = "a-very-secure-secret-key-32chars!!"
SAMPLE_DATA = {
    "access_token": "ya29.test_token",
    "refresh_token": "1//test_refresh",
    "expires_in": 3600,
    "token_type": "Bearer",
}


def test_encrypt_returns_string():
    blob = encrypt_credential(SAMPLE_DATA, SAMPLE_KEY)
    assert isinstance(blob, str)
    assert len(blob) > 0


def test_roundtrip():
    blob = encrypt_credential(SAMPLE_DATA, SAMPLE_KEY)
    result = decrypt_credential(blob, SAMPLE_KEY)
    assert result == SAMPLE_DATA


def test_different_nonce_each_call():
    blob1 = encrypt_credential(SAMPLE_DATA, SAMPLE_KEY)
    blob2 = encrypt_credential(SAMPLE_DATA, SAMPLE_KEY)
    assert blob1 != blob2  # random nonce → different ciphertext


def test_wrong_key_raises():
    blob = encrypt_credential(SAMPLE_DATA, SAMPLE_KEY)
    with pytest.raises(Exception):
        decrypt_credential(blob, "wrong-key-totally-different-32ch")


def test_tampered_blob_raises():
    blob = encrypt_credential(SAMPLE_DATA, SAMPLE_KEY)
    tampered = blob[:-4] + "AAAA"
    with pytest.raises(Exception):
        decrypt_credential(tampered, SAMPLE_KEY)


def test_nested_data():
    data = {"nested": {"a": 1, "b": [1, 2, 3]}, "flag": True}
    assert decrypt_credential(encrypt_credential(data, SAMPLE_KEY), SAMPLE_KEY) == data
