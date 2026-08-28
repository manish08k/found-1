"""
Credential encryption — AES-256-GCM.
Tokens are encrypted at rest; the key lives only in env / secrets manager.
"""
import base64
import hashlib
import json
import os
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Stable salt derived from a fixed label — we don't store a per-key salt
# because the raw key is already a high-entropy secret (≥32 chars enforced
# by pydantic). PBKDF2 here defends against weak/short keys just in case.
_KDF_SALT = b"autoflow-credential-encryption-v1"
_KDF_ITERATIONS = 100_000


def _derive_key(raw: str) -> bytes:
    """Derive a 32-byte AES key from the raw secret using PBKDF2-HMAC-SHA256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_KDF_SALT,
        iterations=_KDF_ITERATIONS,
    )
    return kdf.derive(raw.encode())


def encrypt_credential(data: dict, raw_key: str) -> str:
    """Encrypt a credential dict → base64(nonce + ciphertext)."""
    key = _derive_key(raw_key)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    plaintext = json.dumps(data).encode()
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    blob = base64.urlsafe_b64encode(nonce + ciphertext).decode()
    return blob


def decrypt_credential(blob: str, raw_key: str) -> dict:
    """Decrypt base64(nonce + ciphertext) → credential dict."""
    key = _derive_key(raw_key)
    aesgcm = AESGCM(key)
    raw = base64.urlsafe_b64decode(blob.encode())
    nonce, ciphertext = raw[:12], raw[12:]
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return json.loads(plaintext)
