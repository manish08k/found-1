#!/usr/bin/env bash
# Promote the secondary region's Postgres read replica to a standalone
# writable primary, as part of a region failover.
#
# WHY THIS IS A SEPARATE MANUAL SCRIPT, NOT AUTOMATIC:
# Route53 (infra/terraform/aws/modules/multi-region) will automatically
# flip DNS to the secondary region's API the moment the primary's health
# check fails. That's fine for API traffic — a stateless read/serve
# layer failing over automatically is low-risk. Automatically promoting
# a DATABASE replica to a writable primary on the same trigger is not:
# a transient health-check blip (network flap, one bad AZ) would silently
# fork your data into two writable copies that both accept writes for
# however long the blip lasts, which is a much worse incident than a few
# extra minutes of read-only downtime while a human confirms the primary
# region is actually, genuinely down.
#
# Run this ONLY after confirming via DR_RUNBOOK.md's checklist that this
# is a real region-level event, not a transient health-check failure.
set -euo pipefail

SECONDARY_REGION="${SECONDARY_REGION:?Set SECONDARY_REGION, e.g. us-west-2}"
REPLICA_IDENTIFIER="${REPLICA_IDENTIFIER:?Set REPLICA_IDENTIFIER, e.g. autoflow-production-postgres-replica}"

echo "=================================================================="
echo "REGION FAILOVER — PROMOTING READ REPLICA TO WRITABLE PRIMARY"
echo "Region:   $SECONDARY_REGION"
echo "Replica:  $REPLICA_IDENTIFIER"
echo "=================================================================="
echo
echo "Before continuing, confirm ALL of the following (DR_RUNBOOK.md):"
echo "  [ ] The primary region is confirmed down, not a transient blip"
echo "  [ ] The incident has been declared and the on-call rotation notified"
echo "  [ ] You understand this action is irreversible without a full re-sync"
echo
read -r -p "Type PROMOTE to continue: " confirmation
if [ "$confirmation" != "PROMOTE" ]; then
  echo "Aborted — no changes made."
  exit 1
fi

echo
echo "Promoting $REPLICA_IDENTIFIER in $SECONDARY_REGION..."
aws rds promote-read-replica \
  --region "$SECONDARY_REGION" \
  --db-instance-identifier "$REPLICA_IDENTIFIER"

echo
echo "Promotion initiated. This takes several minutes — poll status with:"
echo "  aws rds describe-db-instances --region $SECONDARY_REGION \\"
echo "    --db-instance-identifier $REPLICA_IDENTIFIER \\"
echo "    --query 'DBInstances[0].DBInstanceStatus'"
echo
echo "NEXT STEPS (see DR_RUNBOOK.md for full procedure):"
echo "  1. Wait for status to reach 'available'"
echo "  2. Update the secondary region's DATABASE_URL secret to point at"
echo "     this instance directly (no longer a replica of the primary)"
echo "  3. Deploy/restart the secondary region's API + workers"
echo "  4. Smoke test before declaring the failover complete"
echo "  5. Once the original primary region recovers, DO NOT just point"
echo "     it back — that region's database is now stale/diverged. Follow"
echo "     the fail-BACK procedure in DR_RUNBOOK.md, which involves"
echo "     re-syncing it as a fresh replica of the new primary first."
