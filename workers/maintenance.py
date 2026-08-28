"""Background maintenance tasks."""
import structlog
from datetime import datetime, timedelta
from sqlalchemy import select, delete

from storage.database import db_context
from storage.models import OAuthCredential, Execution, ExecutionStatus
from credentials.encryption import decrypt_credential
from core.config import settings

log = structlog.get_logger(__name__)


async def refresh_expiring_tokens() -> None:
    """
    Find credentials whose access token expires within 10 minutes
    and proactively refresh them.
    """
    async with db_context() as db:
        result = await db.execute(select(OAuthCredential).where(OAuthCredential.is_valid == True))
        creds = result.scalars().all()

        for cred in creds:
            try:
                token_data = decrypt_credential(cred.encrypted_token, settings.CREDENTIAL_ENCRYPTION_KEY)
                fetched_at = token_data.get("fetched_at")
                expires_in = token_data.get("expires_in")
                refresh_token = token_data.get("refresh_token")

                if fetched_at and expires_in and refresh_token:
                    expiry = datetime.fromtimestamp(fetched_at + expires_in)
                    if expiry - datetime.utcnow() < timedelta(minutes=10):
                        from oauth.flow import refresh_token as do_refresh
                        await do_refresh(cred.id, db)
                        log.info("token_refreshed", credential_id=cred.id, provider=cred.provider)
            except Exception as exc:
                log.error("token_refresh_failed", credential_id=cred.id, error=str(exc))
                cred.is_valid = False
        await db.commit()


async def cleanup_old_executions(days_to_keep: int = 30) -> None:
    """Delete execution rows older than `days_to_keep`."""
    cutoff = datetime.utcnow() - timedelta(days=days_to_keep)
    async with db_context() as db:
        result = await db.execute(
            delete(Execution).where(Execution.created_at < cutoff)
        )
        await db.commit()
        log.info("executions_cleaned", deleted=result.rowcount, cutoff=cutoff.isoformat())
