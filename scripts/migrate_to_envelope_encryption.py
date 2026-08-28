"""
One-time migration: upgrade legacy flat-AES-GCM credential rows
(credentials/encryption.py format) to envelope encryption
(credentials/envelope.py format, per-credential DEK + org-scoped AAD).

Safe to run multiple times — rows already in envelope format are skipped.
Run this once after deploying the envelope-encryption change, then new
credentials (manual DB connections) already write in the new format going
forward; this script catches everything that predates it.

Usage:
    python -m scripts.migrate_to_envelope_encryption
"""
import asyncio
import json

from sqlalchemy import select

from core.config import settings
from credentials.encryption import decrypt_credential
from credentials.envelope import encrypt_credential_envelope
from storage.database import db_context
from storage.models import OAuthCredential, User


async def migrate() -> None:
    migrated, skipped, failed = 0, 0, 0

    async with db_context() as db:
        result = await db.execute(
            select(OAuthCredential, User.org_id).join(User, User.id == OAuthCredential.user_id)
        )
        rows = result.all()

        for cred, org_id in rows:
            try:
                envelope = json.loads(cred.encrypted_token)
                if envelope.get("v") == 2:
                    skipped += 1
                    continue
            except (json.JSONDecodeError, TypeError):
                pass  # not JSON => legacy flat blob, proceed to migrate

            try:
                data = decrypt_credential(cred.encrypted_token, settings.CREDENTIAL_ENCRYPTION_KEY)
                cred.encrypted_token = encrypt_credential_envelope(data, org_id=org_id)
                migrated += 1
            except Exception as e:
                print(f"FAILED to migrate credential {cred.id} ({cred.provider}): {e}")
                failed += 1

        await db.commit()

    print(f"Migration complete: {migrated} migrated, {skipped} already on v2, {failed} failed")
    if failed:
        print("Investigate failures — those rows are still on the legacy format and still work "
              "(decrypt_credential_envelope() falls back automatically), but aren't getting the "
              "per-credential-key benefit yet.")


if __name__ == "__main__":
    asyncio.run(migrate())
