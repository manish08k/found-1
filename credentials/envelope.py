"""
Envelope encryption for credentials.

Why this exists on top of credentials/encryption.py's direct AES-GCM: with
a single static key, one leaked CREDENTIAL_ENCRYPTION_KEY decrypts every
credential for every user, forever, with no way to rotate without
re-encrypting the entire table under load. Envelope encryption fixes both:

  - Each credential gets its own random 256-bit data key (DEK). The DEK
    encrypts the credential data; a master key encrypts (wraps) the DEK.
    Only the small wrapped DEK is ever sent to/through the master key —
    the master key itself never touches the plaintext credential data.
  - Rotating the master key means re-wrapping DEKs (cheap, milliseconds
    per credential) instead of re-encrypting all ciphertext (expensive,
    proportional to the credential's own data size and — across the
    whole table — proportional to your user count).
  - The org_id is bound in as AWS KMS "encryption context" (or, in local
    mode, mixed into the AAD) — a wrapped DEK for org A cannot be
    unwrapped in a request carrying org B's context, so a bug that mixes
    up which org's key to use fails closed instead of silently decrypting
    the wrong org's secrets.

Master key backends (pick one via CREDENTIAL_KMS_PROVIDER):
  - "aws-kms" (recommended for production): master key never leaves AWS
    KMS. Requires CREDENTIAL_KMS_KEY_ID and IAM permissions for
    kms:GenerateDataKey / kms:Decrypt. boto3 handles the actual crypto.
  - "local" (default, dev/small-deployment fallback): master key is
    CREDENTIAL_ENCRYPTION_KEY from settings, same as before this change —
    still gets you per-credential DEKs and org-scoped AAD, just without
    KMS's hardware-backed key custody or its native key-rotation-without-
    re-wrap. Rotating a "local" master key still only requires re-wrapping
    DEKs (see rotate_master_key.py), not re-encrypting credential data.

Storage format (JSON, stored in OAuthCredential.encrypted_token, replacing
the old flat base64 blob — decrypt_credential() below is backward
compatible with pre-envelope rows via a version tag):
  {"v": 2, "wrapped_dek": "<base64>", "nonce": "<base64>",
   "ciphertext": "<base64>", "org_id": "<...|null>", "key_id": "<...>"}
"""
import base64
import json
import os

import structlog
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from core.config import settings
from credentials.encryption import _derive_key  # local master-key derivation, reused

log = structlog.get_logger(__name__)

ENVELOPE_VERSION = 2


def _local_wrap_dek(dek: bytes, org_id: str | None) -> tuple[bytes, str]:
    """Wrap a DEK with the local master key (AAD-bound to org_id)."""
    master_key = _derive_key(settings.CREDENTIAL_ENCRYPTION_KEY)
    aesgcm = AESGCM(master_key)
    nonce = os.urandom(12)
    aad = (org_id or "").encode()
    wrapped = nonce + aesgcm.encrypt(nonce, dek, aad)
    return wrapped, "local"


def _local_unwrap_dek(wrapped: bytes, org_id: str | None) -> bytes:
    master_key = _derive_key(settings.CREDENTIAL_ENCRYPTION_KEY)
    aesgcm = AESGCM(master_key)
    nonce, ciphertext = wrapped[:12], wrapped[12:]
    aad = (org_id or "").encode()
    return aesgcm.decrypt(nonce, ciphertext, aad)


def _kms_wrap_dek(dek: bytes, org_id: str | None) -> tuple[bytes, str]:
    """Wrap a DEK using AWS KMS — the master key never leaves KMS."""
    import boto3
    client = boto3.client("kms", region_name=settings.AWS_REGION or "us-east-1")
    encryption_context = {"org_id": org_id} if org_id else {}
    # We already generated our own DEK (so we control it end-to-end and
    # don't depend on KMS's GenerateDataKey call shape); Encrypt() here
    # wraps that DEK under the CMK.
    resp = client.encrypt(
        KeyId=settings.CREDENTIAL_KMS_KEY_ID,
        Plaintext=dek,
        EncryptionContext=encryption_context,
    )
    return resp["CiphertextBlob"], settings.CREDENTIAL_KMS_KEY_ID


def _kms_unwrap_dek(wrapped: bytes, org_id: str | None) -> bytes:
    import boto3
    client = boto3.client("kms", region_name=settings.AWS_REGION or "us-east-1")
    encryption_context = {"org_id": org_id} if org_id else {}
    resp = client.decrypt(
        CiphertextBlob=wrapped,
        KeyId=settings.CREDENTIAL_KMS_KEY_ID,
        EncryptionContext=encryption_context,
    )
    return resp["Plaintext"]


def _wrap_dek(dek: bytes, org_id: str | None) -> tuple[bytes, str]:
    if settings.CREDENTIAL_KMS_PROVIDER == "aws-kms":
        return _kms_wrap_dek(dek, org_id)
    return _local_wrap_dek(dek, org_id)


def _unwrap_dek(wrapped: bytes, org_id: str | None, key_id: str) -> bytes:
    if settings.CREDENTIAL_KMS_PROVIDER == "aws-kms" and key_id != "local":
        return _kms_unwrap_dek(wrapped, org_id)
    return _local_unwrap_dek(wrapped, org_id)


def encrypt_credential_envelope(data: dict, org_id: str | None = None) -> str:
    """Encrypt a credential dict using envelope encryption. Returns a JSON string."""
    dek = AESGCM.generate_key(bit_length=256)
    aesgcm = AESGCM(dek)
    nonce = os.urandom(12)
    plaintext = json.dumps(data).encode()
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    wrapped_dek, key_id = _wrap_dek(dek, org_id)

    envelope = {
        "v": ENVELOPE_VERSION,
        "wrapped_dek": base64.urlsafe_b64encode(wrapped_dek).decode(),
        "nonce": base64.urlsafe_b64encode(nonce).decode(),
        "ciphertext": base64.urlsafe_b64encode(ciphertext).decode(),
        "org_id": org_id,
        "key_id": key_id,
    }
    return json.dumps(envelope)


def decrypt_credential_envelope(blob: str, org_id: str | None = None) -> dict:
    """
    Decrypt a credential blob. Handles both the new envelope format (v2)
    and the legacy flat-AES-GCM format (pre-migration rows) transparently,
    so this can be dropped in without a hard cutover — see
    scripts/migrate_to_envelope_encryption.py to actively upgrade old rows.
    """
    try:
        envelope = json.loads(blob)
    except (json.JSONDecodeError, TypeError):
        envelope = None

    if not envelope or envelope.get("v") != ENVELOPE_VERSION:
        # Legacy flat blob — fall back to the original direct-AES-GCM path.
        from credentials.encryption import decrypt_credential
        return decrypt_credential(blob, settings.CREDENTIAL_ENCRYPTION_KEY)

    stored_org_id = envelope.get("org_id")
    if stored_org_id != org_id:
        # Fail closed: this credential was encrypted under a different
        # org's context. This should never legitimately happen — it
        # means either a bug passed the wrong org_id, or someone is
        # trying to read a credential that isn't theirs to read.
        log.error("envelope_org_mismatch", expected=org_id, stored=stored_org_id)
        raise ValueError("Credential org context mismatch — refusing to decrypt")

    wrapped_dek = base64.urlsafe_b64decode(envelope["wrapped_dek"])
    nonce = base64.urlsafe_b64decode(envelope["nonce"])
    ciphertext = base64.urlsafe_b64decode(envelope["ciphertext"])

    dek = _unwrap_dek(wrapped_dek, org_id, envelope.get("key_id", "local"))
    aesgcm = AESGCM(dek)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return json.loads(plaintext)
