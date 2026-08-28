"""
Rotate the envelope-encryption master key.

Because credentials use envelope encryption (credentials/envelope.py),
rotating the master key only requires re-wrapping each credential's small
data key (DEK) under the new master key — the actual credential
ciphertext is never touched or re-encrypted. This is what makes routine
key rotation operationally cheap enough to actually do on a schedule,
instead of being a scary one-time migration.

Usage:
    OLD_CREDENTIAL_ENCRYPTION_KEY=... NEW_CREDENTIAL_ENCRYPTION_KEY=... \\
    python -m scripts.rotate_master_key

For the "local" KMS provider only — rotating an AWS KMS CMK is handled by
KMS itself (enable automatic annual rotation on the CMK in the AWS
console/Terraform; KMS keeps old key material versioned internally so
Decrypt keeps working against data wrapped under an older version with no
action needed here).

This only touches rows already in the new envelope format (v2, JSON with
wrapped_dek/nonce/ciphertext). Legacy flat-blob rows are left alone —
run scripts/migrate_to_envelope_encryption.py first if you still have any.
"""
import asyncio
import base64
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select

from credentials.encryption import _derive_key
from storage.database import db_context
from storage.models import OAuthCredential


def _unwrap_with_key(wrapped: bytes, org_id: str | None, raw_key: str) -> bytes:
    master_key = _derive_key(raw_key)
    aesgcm = AESGCM(master_key)
    nonce, ciphertext = wrapped[:12], wrapped[12:]
    aad = (org_id or "").encode()
    return aesgcm.decrypt(nonce, ciphertext, aad)


def _wrap_with_key(dek: bytes, org_id: str | None, raw_key: str) -> bytes:
    master_key = _derive_key(raw_key)
    aesgcm = AESGCM(master_key)
    nonce = os.urandom(12)
    aad = (org_id or "").encode()
    return nonce + aesgcm.encrypt(nonce, dek, aad)


async def rotate() -> None:
    old_key = os.environ["OLD_CREDENTIAL_ENCRYPTION_KEY"]
    new_key = os.environ["NEW_CREDENTIAL_ENCRYPTION_KEY"]
    assert old_key != new_key, "OLD and NEW keys must differ"

    rewrapped, skipped, failed = 0, 0, 0

    async with db_context() as db:
        result = await db.execute(select(OAuthCredential))
        creds = result.scalars().all()

        for cred in creds:
            try:
                envelope = json.loads(cred.encrypted_token)
            except (json.JSONDecodeError, TypeError):
                skipped += 1
                continue
            if envelope.get("v") != 2 or envelope.get("key_id") != "local":
                skipped += 1  # legacy blob, or KMS-wrapped (KMS handles its own rotation)
                continue

            try:
                wrapped_dek = base64.urlsafe_b64decode(envelope["wrapped_dek"])
                org_id = envelope.get("org_id")
                dek = _unwrap_with_key(wrapped_dek, org_id, old_key)
                new_wrapped = _wrap_with_key(dek, org_id, new_key)
                envelope["wrapped_dek"] = base64.urlsafe_b64encode(new_wrapped).decode()
                cred.encrypted_token = json.dumps(envelope)
                rewrapped += 1
            except Exception as e:
                print(f"FAILED to rewrap credential {cred.id}: {e}")
                failed += 1

        await db.commit()

    print(f"Rotation complete: {rewrapped} re-wrapped, {skipped} skipped (legacy/KMS), {failed} failed")
    if failed:
        print("Investigate failures BEFORE removing OLD_CREDENTIAL_ENCRYPTION_KEY from your secrets store.")
    print("\nNext: set CREDENTIAL_ENCRYPTION_KEY to NEW_CREDENTIAL_ENCRYPTION_KEY's value everywhere, "
          "deploy, THEN remove the old key from your secrets store.")


if __name__ == "__main__":
    asyncio.run(rotate())
