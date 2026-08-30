"""
Cryptography / hashing nodes.

Covers:
  hash, hmac, aes_encrypt, aes_decrypt, base64_encode, base64_decode,
  uuid, random_string, jwt_sign, jwt_verify
"""
import base64
import hashlib
import hmac as _hmac
import os
import random
import secrets
import string
import uuid as _uuid
from datetime import datetime, timezone, timedelta
from typing import Any

import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


# ─── crypto.hash ──────────────────────────────────────────────────────────────

@register_node("crypto.hash")
async def crypto_hash(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Hash a string using the specified algorithm."""
    algorithm = config.get("algorithm", "sha256").lower()
    value = config.get("value") or input_data.get("value", "")
    encoding = config.get("encoding", "hex").lower()

    supported = {"md5", "sha1", "sha256", "sha512", "sha3_256", "sha3_512"}
    if algorithm not in supported:
        raise ValueError(f"crypto.hash: unsupported algorithm '{algorithm}' — use one of {supported}")

    h = hashlib.new(algorithm, str(value).encode("utf-8"))
    if encoding == "hex":
        digest = h.hexdigest()
    elif encoding == "base64":
        digest = base64.b64encode(h.digest()).decode()
    elif encoding == "base64url":
        digest = base64.urlsafe_b64encode(h.digest()).decode().rstrip("=")
    else:
        raise ValueError(f"crypto.hash: unsupported encoding '{encoding}' — use hex/base64/base64url")

    return {"hash": digest, "algorithm": algorithm, "encoding": encoding}


# ─── crypto.hmac ──────────────────────────────────────────────────────────────

@register_node("crypto.hmac")
async def crypto_hmac(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Compute an HMAC signature."""
    algorithm = config.get("algorithm", "sha256").lower()
    key = config.get("key") or input_data.get("key", "")
    value = config.get("value") or input_data.get("value", "")
    encoding = config.get("encoding", "hex").lower()

    algo_map = {
        "sha256": hashlib.sha256,
        "sha512": hashlib.sha512,
        "sha1": hashlib.sha1,
        "md5": hashlib.md5,
    }
    if algorithm not in algo_map:
        raise ValueError(f"crypto.hmac: unsupported algorithm '{algorithm}'")

    h = _hmac.new(str(key).encode("utf-8"), str(value).encode("utf-8"), algo_map[algorithm])
    if encoding == "hex":
        sig = h.hexdigest()
    elif encoding == "base64":
        sig = base64.b64encode(h.digest()).decode()
    else:
        raise ValueError(f"crypto.hmac: unsupported encoding '{encoding}'")

    return {"signature": sig, "algorithm": algorithm}


# ─── crypto.aes_encrypt ───────────────────────────────────────────────────────

@register_node("crypto.aes_encrypt")
async def crypto_aes_encrypt(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """AES-256-GCM encrypt a string. key must be 32-byte base64."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore

    key_b64 = config.get("key") or input_data.get("key")
    data_str = config.get("data") or input_data.get("data", "")
    if not key_b64:
        raise ValueError("crypto.aes_encrypt: 'key' (base64) is required")

    try:
        key_bytes = base64.b64decode(key_b64)
    except Exception:
        raise ValueError("crypto.aes_encrypt: 'key' is not valid base64")

    if len(key_bytes) not in (16, 24, 32):
        raise ValueError("crypto.aes_encrypt: key must decode to 16, 24, or 32 bytes")

    nonce = os.urandom(12)  # 96-bit nonce for GCM
    aesgcm = AESGCM(key_bytes)
    plaintext = str(data_str).encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    return {
        "ciphertext_base64": base64.b64encode(ciphertext).decode(),
        "nonce_base64": base64.b64encode(nonce).decode(),
    }


# ─── crypto.aes_decrypt ───────────────────────────────────────────────────────

@register_node("crypto.aes_decrypt")
async def crypto_aes_decrypt(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """AES-256-GCM decrypt. Requires key, ciphertext_base64, nonce_base64."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore

    key_b64 = config.get("key") or input_data.get("key")
    ciphertext_b64 = config.get("ciphertext_base64") or input_data.get("ciphertext_base64")
    nonce_b64 = config.get("nonce_base64") or input_data.get("nonce_base64")

    if not key_b64 or not ciphertext_b64 or not nonce_b64:
        raise ValueError("crypto.aes_decrypt: 'key', 'ciphertext_base64', and 'nonce_base64' are required")

    try:
        key_bytes = base64.b64decode(key_b64)
        ciphertext = base64.b64decode(ciphertext_b64)
        nonce = base64.b64decode(nonce_b64)
    except Exception as exc:
        raise ValueError(f"crypto.aes_decrypt: base64 decode error — {exc}") from exc

    try:
        aesgcm = AESGCM(key_bytes)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except Exception as exc:
        raise ValueError(f"crypto.aes_decrypt: decryption failed — {exc}") from exc

    return {"plaintext": plaintext.decode("utf-8")}


# ─── crypto.base64_encode ─────────────────────────────────────────────────────

@register_node("crypto.base64_encode")
async def crypto_base64_encode(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Base64-encode a string."""
    value = config.get("value") or input_data.get("value", "")
    url_safe = config.get("url_safe", False)
    raw = str(value).encode("utf-8")
    if url_safe:
        encoded = base64.urlsafe_b64encode(raw).decode()
    else:
        encoded = base64.b64encode(raw).decode()
    return {"encoded": encoded}


# ─── crypto.base64_decode ─────────────────────────────────────────────────────

@register_node("crypto.base64_decode")
async def crypto_base64_decode(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Base64-decode a string."""
    value = config.get("value") or input_data.get("value", "")
    url_safe = config.get("url_safe", False)
    try:
        if url_safe:
            raw = base64.urlsafe_b64decode(str(value) + "==")
        else:
            raw = base64.b64decode(str(value) + "==")
        decoded = raw.decode("utf-8")
    except Exception as exc:
        raise ValueError(f"crypto.base64_decode: decode error — {exc}") from exc
    return {"decoded": decoded}


# ─── crypto.uuid ──────────────────────────────────────────────────────────────

@register_node("crypto.uuid")
async def crypto_uuid(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Generate a UUID."""
    version = int(config.get("version", 4))
    if version == 4:
        generated = str(_uuid.uuid4())
    elif version == 1:
        generated = str(_uuid.uuid1())
    elif version == 3:
        namespace_str = config.get("namespace", "dns")
        name = config.get("name", "")
        ns_map = {
            "dns": _uuid.NAMESPACE_DNS,
            "url": _uuid.NAMESPACE_URL,
            "oid": _uuid.NAMESPACE_OID,
            "x500": _uuid.NAMESPACE_X500,
        }
        ns = ns_map.get(namespace_str, _uuid.NAMESPACE_DNS)
        generated = str(_uuid.uuid3(ns, name))
    elif version == 5:
        namespace_str = config.get("namespace", "dns")
        name = config.get("name", "")
        ns_map = {
            "dns": _uuid.NAMESPACE_DNS,
            "url": _uuid.NAMESPACE_URL,
            "oid": _uuid.NAMESPACE_OID,
            "x500": _uuid.NAMESPACE_X500,
        }
        ns = ns_map.get(namespace_str, _uuid.NAMESPACE_DNS)
        generated = str(_uuid.uuid5(ns, name))
    else:
        raise ValueError(f"crypto.uuid: unsupported version {version} — use 1/3/4/5")
    return {"uuid": generated, "version": version}


# ─── crypto.random_string ─────────────────────────────────────────────────────

@register_node("crypto.random_string")
async def crypto_random_string(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Generate a cryptographically-random string."""
    length = int(config.get("length", 32))
    if length < 1 or length > 4096:
        raise ValueError("crypto.random_string: 'length' must be between 1 and 4096")

    charset_name = config.get("charset", "alphanumeric").lower()
    charsets = {
        "alphanumeric": string.ascii_letters + string.digits,
        "alpha": string.ascii_letters,
        "numeric": string.digits,
        "hex": string.hexdigits[:16],  # 0-9a-f
        "lowercase": string.ascii_lowercase,
        "uppercase": string.ascii_uppercase,
        "printable": string.ascii_letters + string.digits + string.punctuation,
    }
    alphabet = charsets.get(charset_name)
    if alphabet is None:
        raise ValueError(f"crypto.random_string: unknown charset '{charset_name}'")

    value = "".join(secrets.choice(alphabet) for _ in range(length))
    return {"value": value, "length": length, "charset": charset_name}


# ─── crypto.jwt_sign ──────────────────────────────────────────────────────────

@register_node("crypto.jwt_sign")
async def crypto_jwt_sign(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Sign a JWT token."""
    import jwt  # PyJWT

    payload = config.get("payload") or input_data.get("payload") or {}
    secret = config.get("secret") or input_data.get("secret")
    algorithm = config.get("algorithm", "HS256")
    expire_minutes = config.get("expire_minutes")

    if not secret:
        raise ValueError("crypto.jwt_sign: 'secret' is required")
    if not isinstance(payload, dict):
        raise ValueError("crypto.jwt_sign: 'payload' must be a dict")

    claims = dict(payload)
    if expire_minutes is not None:
        exp = datetime.now(tz=timezone.utc) + timedelta(minutes=float(expire_minutes))
        claims["exp"] = exp
    if "iat" not in claims:
        claims["iat"] = datetime.now(tz=timezone.utc)

    try:
        token = jwt.encode(claims, secret, algorithm=algorithm)
    except Exception as exc:
        raise ValueError(f"crypto.jwt_sign: signing error — {exc}") from exc

    return {"token": token if isinstance(token, str) else token.decode()}


# ─── crypto.jwt_verify ────────────────────────────────────────────────────────

@register_node("crypto.jwt_verify")
async def crypto_jwt_verify(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Verify and decode a JWT token. Raises on invalid/expired tokens."""
    import jwt  # PyJWT
    from jwt.exceptions import InvalidTokenError

    token = config.get("token") or input_data.get("token")
    secret = config.get("secret") or input_data.get("secret")
    algorithm = config.get("algorithm", "HS256")

    if not token:
        raise ValueError("crypto.jwt_verify: 'token' is required")
    if not secret:
        raise ValueError("crypto.jwt_verify: 'secret' is required")

    try:
        decoded = jwt.decode(token, secret, algorithms=[algorithm])
    except InvalidTokenError as exc:
        raise ValueError(f"crypto.jwt_verify: token invalid — {exc}") from exc

    return {"payload": decoded, "valid": True}
