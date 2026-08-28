# Disaster Recovery Runbook

## Targets

| Scenario | RPO (data loss) | RTO (time to recover) |
|---|---|---|
| Single pod/node failure | 0 | < 2 min (k8s self-heals via HPA/replicas) |
| AZ failure | 0 | < 10 min (multi-AZ Postgres + multi-AZ node groups) |
| Full region failure | < 24h (nightly backup) — improve to <5min once a cross-region streaming replica exists | < 4h (restore from S3 backup into a new region) |
| Accidental data deletion (app bug, bad migration) | < 24h (nightly backup) or < 5min if within Postgres's PITR window | < 2h |
| Full data corruption / ransomware-style event | < 24h | < 6h |

These are **targets to build toward**, not guarantees of the infra as
currently configured — cross-region failover specifically requires setting
up a cross-region read replica and a documented DNS/traffic cutover, which
isn't built yet (see `PRODUCTION_CHECKLIST.md`).

## Who does this

Fill in before this is real:
- **Incident commander (primary on-call):** ___________
- **Database owner:** ___________
- **Escalation path if primary doesn't respond in 15 min:** ___________

See `ONCALL.md` for the rotation.

## Procedure: Restore from backup (region loss or data corruption)

1. **Declare the incident.** Page the on-call rotation, open an incident channel.
2. **Stop writes.** Scale `autoflow-api` and `autoflow-worker` to 0 replicas so nothing writes to a database you're about to replace:
   ```
   kubectl -n autoflow scale deployment/autoflow-api --replicas=0
   kubectl -n autoflow scale deployment/autoflow-worker --replicas=0
   ```
3. **Identify the target restore point.** Latest backup in `s3://autoflow-backups-prod/postgres/`, or a specific timestamp if this is a "restore to before the bad migration" scenario.
4. **Provision a new Postgres instance** (new region if this is a region failure; same region if this is corruption recovery).
5. **Restore:**
   ```
   gunzip -c autoflow-<timestamp>.sql.gz | psql "$NEW_DATABASE_URL_SYNC"
   ```
6. **Update secrets** (`autoflow-secrets` / External Secrets source) to point `DATABASE_URL` at the new instance.
7. **Run `alembic upgrade head`** against the restored database to catch it up on any schema migrations newer than the backup.
8. **Smoke test:** hit `/health`, log in as a test account, list workflows, trigger one manually.
9. **Resume traffic:** scale API/worker back up.
10. **Post-incident:** write down actual RPO/RTO achieved vs. target, file follow-ups for the gap.

## Procedure: Region failover (once cross-region replica exists)

Not yet built. When it is, this section should cover: promoting the
replica to primary, updating DNS/global load balancer to point at the new
region, and the reverse procedure for failing back once the original
region recovers.

## Things to verify regularly, not just write down once

- Backup restore test runs monthly and actually alerts someone on failure (`.github/workflows/backup-restore-test.yml`) — treat a failed restore test as an incident, not a flaky CI job.
- Whoever is "database owner" above can actually get AWS/cloud console access under pressure, not just in theory.
- This document itself gets reviewed after every real incident that touches it.
