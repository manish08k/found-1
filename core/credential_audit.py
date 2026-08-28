"""
Credential access audit trail + anomaly detection.

Every time a credential is decrypted (oauth/flow.py's get_credential_data
and get_access_token), we now know a *credential exists* was already
logged (the audit_logs table already records create/update), but not who
has been *using* it since. This closes that gap:

  - Every decrypt writes an AuditLog row (action="credential:access") —
    who, when, which credential, which provider, from which org.
  - A Redis counter tracks decrypts-per-credential-per-minute. Crossing a
    threshold logs a structured "credential_access_anomaly" warning
    (something a log-based Alertmanager/Loki rule can page on) rather
    than silently continuing — a credential normally used a handful of
    times an hour suddenly being decrypted hundreds of times in a minute
    is either a runaway workflow loop or a stolen credential ID being
    hammered by someone else.

Kept deliberately lightweight (one Redis INCR, one DB insert) since this
runs on the hot path of every node execution that uses a credential — the
whole point is this can't be the thing that makes the platform slow.
"""
import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from storage.models import AuditLog

log = structlog.get_logger(__name__)

_redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)

# Decrypts of the SAME credential within one minute above this threshold
# triggers an anomaly log. Tune based on real usage once you have a
# baseline — a workflow polling every few seconds legitimately decrypts
# its credential ~20x/min, so this starts well above that.
ANOMALY_THRESHOLD_PER_MINUTE = 120


async def log_credential_access(
    db: AsyncSession,
    credential_id: str,
    user_id: str,
    org_id: str | None,
    provider: str,
) -> None:
    db.add(AuditLog(
        org_id=org_id,
        user_id=user_id,
        action="credential:access",
        resource_type="credential",
        resource_id=credential_id,
        meta={"provider": provider},
    ))
    # Caller (oauth/flow.py) already runs inside a request/execution that
    # commits its own session — don't force a commit here, just enqueue
    # the row, consistent with core/audit.py's write_audit_log().

    try:
        key = f"cred_access:{credential_id}"
        count = await _redis.incr(key)
        if count == 1:
            await _redis.expire(key, 60)
        if count == ANOMALY_THRESHOLD_PER_MINUTE:
            # Only fire once per window (== not >=) so this doesn't spam
            # a warning on every single decrypt past the threshold.
            log.warning(
                "credential_access_anomaly",
                credential_id=credential_id,
                user_id=user_id,
                org_id=org_id,
                provider=provider,
                count_last_minute=count,
            )
    except Exception:
        # Anomaly detection is a bonus signal, not a correctness
        # requirement — Redis being down shouldn't block a credential
        # decrypt that a workflow actually needs to run.
        log.warning("credential_audit_redis_unavailable")
