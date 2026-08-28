# Production Readiness Checklist — AutoFlow at ~1M Users

Everything below is now in this repo. Nothing here is meant to be applied
blind — placeholders (passwords, webhook URLs, account IDs, ARNs) must be
filled in, and anything touching real data (the partitioning migration,
DR restore procedure) should be dry-run in staging first.

## Application

| Item | File(s) |
|---|---|
| SQL database node (query/execute, encrypted credentials, parameterized only) | `integrations/database/handler.py`, `api/routes/credentials.py`, frontend `CredentialsPage`/`NodePanel`/`nodes.ts` |
| Per-user (not just per-IP) rate limiting | `api/middleware/rate_limit.py`, wired in `main.py` |
| Idempotency keys on triggers/webhooks/executions | `api/middleware/idempotency.py`, wired in `main.py` |
| Read replica routing (execution history, workflow list, DLQ) | `storage/database.py` (`get_db_read`), used in `api/routes/executions.py`, `workflows.py`, `dlq.py`. Set `DATABASE_URL_REPLICA` once a replica exists — falls back safely to primary until then. |

## Data layer

| Item | File(s) |
|---|---|
| Connection pooling | `k8s/25-pgbouncer.yml` |
| Executions table partitioning (monthly) | `storage/migrations/versions/6a5de1399ff2_partition_executions.py` — **read the docstring, test on a staging copy first** |
| Nightly backups → S3, with retention | `k8s/29-backup-cronjob.yml` |
| Automated monthly restore test | `.github/workflows/backup-restore-test.yml` |
| Secrets pulled from AWS Secrets Manager (not committed) | `k8s/28-external-secrets.yml` |

## Scaling & delivery

| Item | File(s) |
|---|---|
| Worker autoscaling on queue depth (KEDA) | `k8s/26-worker-autoscale.yml` |
| Canary deploys with automated rollback | `k8s/10b-api-rollout.yml` (Argo Rollouts), wired into `.github/workflows/ci-cd.yml` |
| Staging environment mirroring prod topology | `k8s/kustomization.yaml` + `k8s/overlays/staging`, `k8s/overlays/production` |
| CI: test → coverage gate → Trivy scan → cosign sign → verify → deploy → auto-rollback | `.github/workflows/ci-cd.yml` |
| Load testing against staging (k6) | `loadtest/basic_load.js`, `.github/workflows/load-test.yml` |

## Network & edge

| Item | File(s) |
|---|---|
| Kubernetes NetworkPolicies (default-deny + explicit allows) | `k8s/27-network-policies.yml` |
| CDN + WAF + edge rate limiting (Cloudflare, Terraform) | `infra/terraform/cloudflare/main.tf` — swap for CloudFront/AWS WAF or Fastly if that's your cloud; the pattern's the same |

## Observability & operations

| Item | File(s) |
|---|---|
| Alert rules (error rate, latency, queue backlog, DLQ growth, DB/Redis pressure) | `monitoring/alert-rules.yml` |
| Alert routing (page vs. warn) | `monitoring/alertmanager.yml` — **put real Slack/PagerDuty values in**, currently placeholders |
| Metrics exporters (Postgres, Redis) | `docker-compose.yml` |
| On-call rotation + response expectations | `ONCALL.md` — **fill in actual names** |
| Disaster recovery runbook with RTO/RPO targets | `DR_RUNBOOK.md` |

## Position (role) authorization

| Item | File(s) |
|---|---|
| Role-gated database credentials — only `admin`/`owner` in an org can add a raw DB connection | `api/middleware/rbac.py` (`credential:database:manage`), enforced in `api/routes/credentials.py` |
| Role-gated write-capable nodes — only `admin`/`owner` can save a workflow containing `database.execute` | `api/middleware/rbac.py` (`workflow:use_database_execute`, `check_write_db_permission`), enforced in `api/routes/workflows.py` create/update |
| Run-time re-check, not just save-time | `core/execution_engine.py` — re-checks the workflow owner's current role immediately before running, so a role downgraded *after* a workflow was saved actually takes effect |
| Solo/personal accounts (no org) are not blocked | `user_has_permission()` / `require_permission_or_personal()` — role gating separates teammates within an org, it doesn't restrict someone from their own data |
| Tests | `tests/test_rbac_database_permissions.py` |

`database.query` (read-only) is intentionally **not** gated the same way — any role that can build workflows at all can read via that node; only the write path (`database.execute`) and adding the underlying credential require elevated role.

## SQL integration — verified against a live database, not just unit-tested

Actually installed MariaDB in the build sandbox, seeded a real `customers`
table, and ran `integrations/database/handler.py`'s functions against it
directly (not mocked):
- `database.query` executed a parameterized `SELECT ... WHERE status = :status` and returned the right 2 rows.
- The read-only guard correctly rejected a `DELETE` statement.
- `database.execute` ran a parameterized `UPDATE`, and a follow-up `SELECT` confirmed the write actually landed.
- A `'; DROP TABLE customers; --` string passed as a **bound parameter** matched 0 rows and left the table with all 3 rows intact — confirming parameters are data, never executable SQL.

This surfaced one real bug, now fixed: `pool_pre_ping=True` combined with
`aiomysql==0.2.0` and SQLAlchemy 2.0.35 caused every MySQL connection
checkout to fail (`ping() missing 1 required positional argument`) — a
version-compatibility issue between those two libraries, not something
visible from reading the code. Fixed by disabling `pool_pre_ping`
specifically for the mysql dialect in `_get_engine()` (Postgres/SQLite
still get it). The exact scenario is preserved as an opt-in regression
test: `tests/test_database_integration.py::test_live_mysql_query_execute_and_injection_safety` (`RUN_LIVE_DB_TESTS=1` + `LIVE_MYSQL_*` env vars).

**To connect your own MySQL**: this sandbox can't reach a database on
your network (no route to it from here), so I tested against a local
instance instead. In the app itself, use the UI: Credentials → *Add
Database* → MySQL, fill in your real host/port/user/password/database.
Everything above proves the code path those fields feed into actually
works.

## Credential & account security — verified live, not just written

Built and actually ran end-to-end against live Postgres + Redis in the
build sandbox (register → login → MFA → refresh → logout), not just
unit-tested in isolation:

| Item | File(s) | Verified |
|---|---|---|
| Envelope encryption (per-credential DEK, org-scoped AAD, KMS-pluggable) | `credentials/envelope.py`, wired into `oauth/flow.py`'s manual-credential path | Roundtrip, wrong-org-id fails closed, two credentials with identical plaintext get different ciphertext, legacy blobs still decrypt — all 4 verified live (`tests/test_envelope_encryption.py`) |
| Master key rotation without re-encrypting data | `scripts/rotate_master_key.py` | Re-wraps DEKs only; see script docstring for usage |
| Legacy → envelope migration | `scripts/migrate_to_envelope_encryption.py` | One-time, safe to re-run |
| Credential access audit logging | `core/credential_audit.py`, called from `oauth/flow.py` on every decrypt | Confirmed a real `AuditLog` row is written on every `get_credential_data()` call, with provider/user/org |
| Anomaly detection (decrypt volume per credential) | `core/credential_audit.py` (`ANOMALY_THRESHOLD_PER_MINUTE`) | Logs a structured warning a Loki/Alertmanager rule can page on — threshold not yet tuned against real usage |
| Short-lived access tokens (15 min) + rotating refresh tokens | `api/middleware/auth.py`, `api/middleware/refresh_tokens.py` | Full register→login→refresh flow run live; rotation confirmed (new token ≠ old) |
| Refresh token reuse detection | `api/middleware/refresh_tokens.py` (`rotate_refresh_token`) | Replaying an already-rotated token live returned 401 AND revoked the entire session chain — confirmed both the replayed token and its successor stopped working |
| Immediate access-token revocation (logout) | `api/middleware/auth.py` (`revoke_access_token`, jti deny-list) | `/api/auth/logout`, `/api/auth/logout-everywhere` |
| Per-account lockout (independent of source IP) | `api/middleware/auth.py` (`check_account_lockout`) | 6 failed logins live → 423 Locked, confirmed distinct from the pre-existing per-IP limiter |
| MFA (TOTP), mandatory for admin/owner roles | `api/middleware/mfa.py`, `api/routes/auth.py` | Full live flow: forced enrollment on first login as an org owner → scoped `mfa_setup` token (confirmed it does NOT work as a general bearer token) → QR/secret issued → real TOTP code verified → session issued → next login correctly demands a code → wrong code rejected, right code accepted |
| Tests | `tests/test_envelope_encryption.py`, `tests/test_mfa.py`, `tests/test_auth_middleware.py` (rewritten — the pre-existing version referenced an in-memory dict that no longer exists in the Redis-backed implementation) | 37 passing |

**Bugs this testing found and fixed**, not just theoretical:
- `pool_pre_ping=True` broke every MySQL connection under aiomysql 0.2.0 + SQLAlchemy 2.0.35 (see the SQL integration section above).
- The new `refresh_tokens` table's migration used `String(36)` for `user_id`/`id`/`replaced_by_id`, but `users.id` is actually Postgres `UUID` — the foreign key failed outright. Fixed to use the same `UUID(as_uuid=False)` type, then re-verified upgrade AND downgrade against a live Postgres.
- The pre-existing `tests/test_auth_middleware.py` imported a module-level `_login_attempts` dict that didn't exist in the actual (Redis-backed, async) implementation — the whole file was silently broken before this pass. Rewritten to test the real implementation.

**Still open / needs a human decision:**
- `ANOMALY_THRESHOLD_PER_MINUTE` (120) is a starting guess — tune it against real usage once you have a baseline, and actually wire the `credential_access_anomaly` log line into an Alertmanager/Loki rule (not done yet — it logs, nothing pages on it today).
- Least-privilege DB user guidance (encourage a read-only DB user for `database.query`-only use cases) is a UI/docs improvement, not built.
- Vault-issued dynamic (short-lived, auto-rotating) database credentials instead of a static password is the next step up from what's here — bigger infra lift, not started.
- mTLS between API/worker/database (Istio/Linkerd) — NetworkPolicies control *who* can talk to whom; mTLS additionally protects *that traffic in flight*, not built.
- `tests/test_execution_engine.py::test_node_timeout_raises` hangs (pre-existing, unrelated to this pass) — worth a look, but out of scope here.
- CI now includes gitleaks, Bandit, and pip-audit (`.github/workflows/ci-cd.yml`) plus container hardening — read-only root filesystem + dropped Linux capabilities on every pod (`k8s/10-api.yml`, `10b-api-rollout.yml`, `20-worker-beat.yml`, `25-pgbouncer.yml`). All new and unweathered against this codebase; expect some initial noise to triage on the first real CI run.



- **Fill in every placeholder**: `CHANGE_ME` passwords, `ACCOUNT_ID`/role ARNs in `k8s/28-external-secrets.yml`, Slack/PagerDuty values, Cloudflare zone ID, on-call names.
- **Install the operators these manifests assume exist**: KEDA, Argo Rollouts, External Secrets Operator, a NetworkPolicy-enforcing CNI (Calico/Cilium).
- **Cross-region failover** — `DR_RUNBOOK.md` flags this as not yet built (needs a cross-region replica + a documented DNS cutover). Nightly S3 backups get you region-loss recovery in hours, not the minutes true active-active would give you.
- **Raise the CI coverage gate** over time — it starts at 40% so it doesn't block unrelated PRs on day one; ratchet it up deliberately as coverage improves.
- **Actually run the load test against staging before your first real traffic spike** — the k6 script's `TARGET_VUS` default is a guess, not a validated number for your actual usage pattern.

## Marketplace + UX pass — verified live and against the real TS compiler

**Marketplace (was scaffolded backend, no frontend, no content — now functional end-to-end):**
- `core/marketplace.py`'s `install_item()` now actually creates a real, editable `Workflow` row in the installing user's workspace (installed `inactive`, since credentials still need connecting) — previously it only incremented a download counter and hoped the frontend would do something with the returned JSON.
- `scripts/seed_marketplace_templates.py` — 8 real starter templates built from the actual node catalog (Slack alerting, GitHub→Notion, scheduled DB report, HubSpot→Sheets, WhatsApp order confirmation, Airtable→Slack sync, HTTP health check monitor, GitHub release→Discord). Ran live: all 8 seed correctly, browse/search/category-filter/get/install all verified via the real HTTP app, install confirmed to produce a real workflow with the right node count.
- `frontend/src/components/pages/MarketplacePage.tsx` (new) — browse grid, search, category filter, detail panel, install button that jumps straight into the editor with the installed workflow open. Wired into `Sidebar`/`Dashboard`/`store`.
- Honest framing preserved: this is 8 official templates, not "thousands of community templates" — see the earlier percentage breakdown in conversation. The shelf is real; filling it further needs real users publishing real solutions.

**UX pass:**
- `frontend/src/components/common/ExpressionInput.tsx` (new) — typing `{{` in any text/textarea config field now opens autocomplete suggestions computed from the actual upstream node graph (BFS backward through edges) plus trigger fields, with arrow-key navigation. Wired into `NodePanel` for all `text`/`textarea` fields; `WorkflowEditor` now passes the full node/edge graph down so suggestions are accurate per-node, not generic.
- `NodePicker` — search now also matches node descriptions (previously label/type/category only), added arrow-key navigation + Enter-to-add, and a real empty-state with a "clear search" action instead of a bare "No nodes found".
- `AutoflowNode` (canvas node) — failed nodes now show the actual error message inline (truncated, full text on hover), not just a red border with no way to see what broke without opening the executions panel.

**Bug found and fixed by running the real TypeScript compiler** (installed frontend deps and ran `tsc --noEmit`, not just eyeballing the diff): `WorkflowEditor.tsx`'s `addNode()` had a duplicate `type` key in the new node's `data` object — pre-existing, unrelated to this pass, harmless in practice (both resolved to the same value) but a genuine TS error. Fixed.

**Pre-existing, NOT fixed (out of scope for this pass, flagging so it isn't lost):** `tsc --noEmit` shows 7 remaining errors in `Dashboard.tsx`, `CredentialsPage.tsx`, and `TriggersPanel.tsx`, all the same root cause — a `providersApi`-shaped React Query hook typing mismatch. These predate this session's changes.

## Frontend auth flow — fixed the critical gap, verified against a live server

The backend's MFA/refresh-token/lockout work (an earlier pass) was never
wired into the frontend — `LoginPage.tsx` assumed `login()` always
returned `{access_token}`, so **any admin/owner account could not log in
through the UI at all**, and no session ever refreshed (silent 15-minute
logouts). Fixed:

- `frontend/src/api/client.ts` — `authApi.login()` now returns one of three
  real shapes and the caller branches on it; refresh token is stored
  alongside the access token; the 401 interceptor tries `/auth/refresh`
  once (de-duped across concurrent requests) before giving up and
  redirecting to login; `authApi.logout()` calls the real endpoint so the
  refresh token is revoked server-side, not just forgotten client-side.
- `frontend/src/components/LoginPage.tsx` — added the `mfa_code` step
  (plain 6-digit input) and `mfa_enroll` step (QR code + manual secret +
  verify) for accounts whose role requires MFA.
- `frontend/src/components/sidebar/Sidebar.tsx` — logout now calls
  `authApi.logout()` instead of only clearing `localStorage`.

**Verified two ways, not just compiled:**
1. `npx tsc --noEmit` (real dependencies installed, not just brace-counting) — zero errors in any file touched, same 7 pre-existing unrelated errors as before.
2. Booted the actual backend as a real HTTP server (not in-process ASGI) and hit it with `axios` using the *exact* request/response shapes `client.ts` uses — register, login, `/me`, refresh, logout, and confirmed the access token is actually rejected after logout (401). All passed.

## The 7 remaining gaps — closed, with real verification not just files

### 1. Infrastructure-as-code (Terraform)
`infra/terraform/aws/` — VPC (multi-AZ, public/private subnets, NAT), EKS
(on-demand + spot node groups), RDS Postgres (Multi-AZ primary + read
replica), ElastiCache Redis (replication group, auto-failover), S3
backups bucket with cross-region replication, cost alerting. All HCL
syntax-validated with `python-hcl2` (the `terraform` binary itself
couldn't be installed — its releases CDN isn't in this sandbox's network
allowlist). Provider-alias inheritance for the two secondary providers
(replica region, us-east-1 billing) was fixed to the technically-correct
pattern (`configuration_aliases` + explicit `providers = {}` passthrough)
rather than the common mistake of redeclaring an aliased provider inside
a child module. `infra/terraform/aws/README.md` covers apply order and
what to fill in before a real `terraform apply`.

### 2. Frontend E2E tests (Playwright)
`frontend/e2e/` — auth (register, wrong-password, per-account lockout,
logout), marketplace (browse/search/install/empty-state), workflow
builder (node search including the description-match improvement,
keyboard nav, expression autocomplete), accessibility (axe-core scans +
keyboard-only login). **Written and fully type-checked** against the
real Playwright/axe-core types (`npx tsc --noEmit -p tsconfig.e2e.json`
→ 0 errors) but **not executed** — this sandbox's network policy
explicitly blocks `cdn.playwright.dev` (confirmed via the actual 403
error, not assumed). See `frontend/e2e/README.md` for exact run
instructions somewhere with real network access.

### 3. Real (small-scale) load test — actually run, not simulated
Installed the real k6 binary (from GitHub releases, an allowed domain)
and ran it against the actual live backend. This **found two real bugs**:
- `asyncpg.exceptions.TooManyConnectionsError` under 900 concurrent
  requests — direct, reproducible proof of the exact connection-exhaustion
  failure mode PgBouncer (`k8s/25-pgbouncer.yml`) was built to prevent,
  not just a theoretical concern.
- The load test script itself had two bugs, found by running it: sharing
  one auth token across all virtual users meant it was accidentally
  testing the per-user rate limiter's rejection behavior instead of
  realistic multi-user load (fixed — `setup()` now registers a distinct
  account pool); and k6's JS engine doesn't support object spread syntax
  (fixed — `Object.assign` instead).
- Full writeup with real numbers, both bugs, and honest scope caveats
  (single sandbox box, not real cloud capacity): `loadtest/RESULTS.md`.

### 4. Multi-region automation
`infra/terraform/aws/modules/multi-region/` — Route53 health-check
failover (automatic DNS cutover) + `promote.sh`, a **deliberately
manual** database-replica-promotion script with a typed confirmation
step. Documented why promotion is manual, not automatic: auto-promoting
a database on a transient health-check blip risks forking writable data
across two regions, which is worse than a few extra minutes of downtime
while a human confirms it's a real outage. Not applied by default (roughly
doubles infra cost) — opt-in, see the module's header comment.

### 5. Legal/compliance
- `PRIVACY_POLICY.md` / `TERMS_OF_SERVICE.md` — templates, explicitly
  marked as not legal advice and requiring real counsel review, with
  `[BRACKETED]` placeholders for jurisdiction-specific decisions.
- **Real, working code**, not just policy text: `api/routes/privacy.py`
  — `GET /api/privacy/export` (full account data export, credential
  METADATA only, never decrypted secrets) and `DELETE /api/privacy/account`
  (typed confirmation + password re-entry required, cascades through
  existing FK constraints, anonymizes rather than deletes audit log
  entries — the standard defensible pattern for erasure vs. legitimate
  security record-keeping). **Ran live against the real app**: export
  returned real data, deletion correctly rejected a wrong confirmation
  phrase (400) and wrong password (401), real deletion succeeded (204),
  and — critically — confirmed the account was actually gone afterward
  (login attempt correctly failed with 401).

### 6. Cost alerting
`infra/terraform/aws/modules/cost-alerts/` — AWS Budgets at 50/80/100/120%
thresholds plus a forecasted-spend warning, and a separate CloudWatch
billing alarm (belt-and-suspenders, since it reads actual billing metrics
rather than the Budgets service's own evaluation cycle). No default
email — apply fails closed rather than silently alerting nowhere.

### 7. Accessibility
Real fixes, not just a test suite: 6 icon-only buttons across
`NodePicker`, `NodePanel` (close + delete), `MarketplacePage`,
`TriggersPanel`, `ExecutionsPanel`, and `Sidebar` (nav + logout) were
missing accessible names — found by grepping for icon-only `<button>`
elements and checking each one, not guessed at. Added `aria-label`
(and `aria-current="page"` on the active nav item). The axe-core
automated scan suite (`frontend/e2e/accessibility.spec.ts`) exists but
couldn't run for the same Playwright-browser network reason as item 2 —
so this pass is "the accessibility issues findable by manual code review
were fixed", not "confirmed zero WCAG violations by an actual scan".

## What's still genuinely open after all of this

- None of the Terraform has been `terraform apply`'d anywhere — it's
  reviewed and syntax-valid, not battle-tested against a real AWS account.
- The E2E and accessibility test suites need to actually run somewhere
  with normal network access before they provide real confidence, not
  just "this compiles."
- The load test's real numbers are from a single sandboxed box, not the
  target k8s deployment — re-run against a real staging environment with
  PgBouncer in front to confirm the connection-exhaustion bug is actually
  fixed by it, not just theoretically addressed.
- Legal documents still need an actual lawyer, not just careful placeholder-marking.

## Integration catalog expanded — honestly, not to close the gap, to narrow it

n8n has 400+ integrations built over years by a full team + community —
that gap doesn't close from one more coding pass, and claiming otherwise
would be dishonest. What's real: 4 new, genuinely working integrations
were added, bringing the catalog from ~16 to 20.

| Integration | Node types | Credential | File |
|---|---|---|---|
| Stripe | `create_payment_link`, `get_customer`, `list_charges`, `create_refund` | API key (secret key) | `integrations/stripe_/handler.py` |
| Email (SendGrid) | `send` | API key | `integrations/email_/handler.py` |
| Twilio | `send_sms` | Account SID + Auth Token | `integrations/twilio_/handler.py` |
| Jira | `create_issue`, `search_issues`, `add_comment` | Domain + email + API token | `integrations/jira_/handler.py` |

Backend: `POST /api/credentials/api-key` — a new generic endpoint reusing
the same envelope encryption and role-gating as database credentials
(same risk profile: a static secret, decrypted server-side only for the
duration of one node run). Frontend: a matching "Add API Key" form in
`CredentialsPage.tsx`, node catalog entries with real config fields in
`frontend/src/types/nodes.ts`, and 3 new marketplace starter templates
using them (`scripts/seed_marketplace_templates.py`, now 11 total).

**Tested honestly, given a real constraint**: this sandbox's network
egress is restricted to package registries — `api.stripe.com`,
`api.sendgrid.com`, `api.twilio.com`, and `*.atlassian.net` aren't
reachable, so a live-API test like the MySQL integration got wasn't
possible here. Used `respx` to mock the HTTP boundary instead
(`tests/test_new_integrations.py`, 17 tests, all passing) — this verifies
request construction (URLs, auth scheme, payload shape, e.g. confirming
Jira's description field is correctly wrapped in Atlassian Document
Format rather than sent as a plain string) and response parsing, which
is the part actually under this project's control. It would **not** catch
a live-API surprise the way the MySQL `pool_pre_ping` bug was caught —
that class of finding needs a real account with each service, which
whoever deploys this should budget time for before relying on these in
production.

**What this does and doesn't mean**: the integration-count gap moved
from ~16 vs 400+ to ~20 vs 400+. That's real, incremental progress, not
a claim of parity. The other two gaps flagged as un-closeable by code
alone — battle-testing and community-contributed content — are exactly
as open as before, because they genuinely can't be manufactured; they
need real users and real time, which is true regardless of how much more
code gets written.

## Second integration batch: Trello, PagerDuty, Asana, AWS S3

Same pattern as the first batch (Stripe/SendGrid/Twilio/Jira), same
honesty about what live-testing could and couldn't cover here.

| Integration | Node types | Credential | File |
|---|---|---|---|
| Trello | `create_card`, `move_card`, `list_cards` | API key + token | `integrations/trello_/handler.py` |
| PagerDuty | `trigger_incident`, `resolve_incident` | Events API routing key | `integrations/pagerduty_/handler.py` |
| Asana | `create_task`, `complete_task`, `list_tasks` | Personal access token | `integrations/asana_/handler.py` |
| AWS S3 | `put_object`, `get_object`, `list_objects`, `generate_presigned_url` | Access key + secret | `integrations/aws_s3_/handler.py` |

Integration count: ~20 → 24. Marketplace templates: 11 → 13 (added
"Health Check Failure → PagerDuty Incident", "New Stripe Customer →
Asana Onboarding Task", "Daily Report → S3 Archive"), verified by
actually running the seed script against a fresh database — all 13
created with zero errors.

**Tested honestly**: `tests/test_more_integrations.py` (Trello/PagerDuty/
Asana, mocked via `respx` — 16 tests) and `tests/test_s3_integration.py`
(AWS S3, mocked via `moto` since `amazonaws.com` isn't reachable from
this sandbox either — 7 tests, including real edge cases: binary content
falling back to base64, the 10MB size cap actually rejecting an oversized
object, presigned URL generation). All 21 pass. Same caveat as the first
batch: this verifies request/response handling, not live-API behavior —
budget real testing time with actual accounts before relying on these in
production.

**On deploying the Terraform to a real AWS account**: not done, and
can't honestly be done from here — no AWS credentials, and this
sandbox's network doesn't reach AWS's API endpoints at all (confirmed:
only specific package registries are allowlisted, not `*.amazonaws.com`).
The Terraform is reviewed and HCL-syntax-valid (see the earlier section),
not battle-tested against a real account. That step needs someone with
real AWS access to run `terraform apply` and work through whatever
account-specific issues come up (IAM permission boundaries, service
quotas, etc.) that can't be caught by static review.

## Where the integration/marketplace gap actually stands now

~24 integrations vs n8n's 400+. Real progress (16 → 24 across two
sessions), still nowhere near parity — and won't be from more solo
coding passes at this rate. The two gaps that were correctly flagged as
un-closeable by code (battle-testing, community-contributed content)
remain exactly as open as before, because they still can't be
manufactured. Everything that COULD be closed by more code has had real,
honest progress made on it each time it's been asked for.

## Plan/billing enforcement — real gap closed, not just a pricing table added

`Organization.plan`, `max_workflows`, and `max_executions_per_day` existed
on the model before this pass but were never read anywhere — any org on
any plan had unlimited everything. This closes that.

| Item | File(s) |
|---|---|
| 5-tier limits config matching the pricing table exactly | `core/plans.py` |
| Active-workflow limit enforcement | `api/routes/workflows.py` (`activate_workflow`) |
| Monthly execution limit — checked at the HTTP layer (immediate 402) AND inside the execution engine itself (catches webhook/scheduled triggers that don't have an HTTP caller to reject) | `api/routes/workflows.py`, `core/execution_engine.py` |
| Per-org user limit | `api/routes/orgs.py` (`invite_member`) |
| Execution-history retention window | `api/routes/executions.py` (`list_executions`) |
| New audit-log endpoint, gated by role AND plan tier (Business+) | `api/routes/orgs.py` (`GET /audit-log`) — this endpoint didn't exist before; the `audit:read` permission was defined but unused |
| `business` plan tier added to the DB enum | `storage/migrations/versions/002df4995e73_add_business_plan_tier.py` — migration tested for real: stamped back a revision, ran upgrade, confirmed via `SELECT unnest(enum_range(NULL::orgplan))` that `business` landed between `pro` and `enterprise` |
| Billing API (plan catalog + live usage) | `api/routes/billing.py` |
| Pricing page rendering the table from real backend data, with a live usage widget | `frontend/src/components/pages/PricingPage.tsx` |
| Tests | `tests/test_plans.py` — 12 tests confirming every number in the table matches `core/plans.py` exactly |

**Verified live, not just unit-tested**: ran the full flow against a real
Postgres — solo/personal accounts confirmed genuinely unmetered (created
+ activated 7 workflows with zero limit hits), a Free-plan org correctly
blocked at exactly its 6th active-workflow attempt (402, with a clear
upgrade message), the audit-log endpoint correctly returned 402 on Free
and 200 after upgrading the same org to Business, and the plans catalog
endpoint confirmed to match the pricing table field-for-field.

**Deliberately NOT built**: real payment processing. `POST
/api/billing/upgrade-request` records the request (visible in the org's
own audit log) rather than faking a checkout success — wiring a live
merchant account, webhook signature verification, and subscription
lifecycle handling is a real system on its own, and faking success here
would be actively worse than the honest "we'll follow up" it does now.
The Stripe integration built earlier in this project
(`integrations/stripe_/handler.py`) has the REST call pattern to build
real checkout on top of, once there's an actual Stripe merchant account
behind it.

## Real Stripe subscription billing — genuinely wired, not a stub

The earlier "upgrade-request" flow (audit-logged, no real checkout) is
still there as a fallback, but there's now a **real** path:

| Item | File(s) |
|---|---|
| Checkout Session creation (real Stripe API contract) | `core/stripe_billing.py` (`create_checkout_session`) |
| Webhook signature verification — implements Stripe's documented HMAC-SHA256 scheme directly, constant-time comparison, replay-window check | `core/stripe_billing.py` (`verify_webhook_signature`) |
| Webhook → plan sync (`checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`) | `core/stripe_billing.py` (`apply_webhook_event`) |
| `POST /api/billing/checkout`, `POST /api/billing/webhook` | `api/routes/billing.py` |
| `stripe_customer_id`, `stripe_subscription_id`, `subscription_status` on Organization | `storage/models.py` + migration `9d5a798800b8` |
| Frontend: real checkout redirect, with graceful fallback to the manual-request flow if Stripe isn't configured | `frontend/src/components/pages/PricingPage.tsx` |

**What "real" means here, precisely**: this uses Stripe's actual REST API
shape (Checkout Sessions, webhook signature scheme) — not a mock, not a
fake success response. What it cannot do without a real Stripe merchant
account (STRIPE_SECRET_KEY/STRIPE_WEBHOOK_SECRET/price IDs — all empty
by default, see `core/config.py`) is complete an actual charge. That's
not a limitation of this build environment — it's true of any Stripe
integration on earth before a merchant account exists. `BillingNotConfigured`
makes this fail loudly (501, clear message) rather than silently.

**Verified for real, three ways**:
1. **Actual cryptography, not mocked**: hand-built a correctly-HMAC-signed webhook exactly as Stripe would, confirmed it verifies; confirmed a tampered payload, wrong secret, and expired timestamp are each independently rejected; confirmed a malformed header is rejected. All 5 checks are real HMAC-SHA256 math, zero network involved.
2. **Request construction** (mocked transport, `respx`, same honesty as the other Stripe integration): confirmed the Checkout Session request has the right auth, subscription mode, price ID, and org-linkage metadata; confirmed the Free plan correctly refuses checkout (nothing to purchase).
3. **Live database state**, real Postgres: ran the actual migration (stamped back, upgraded, confirmed the new columns + unique constraints exist), then fed all three webhook event types through `apply_webhook_event` against a real org row — confirmed `checkout.session.completed` sets the plan/customer/subscription IDs, `customer.subscription.updated` (past_due) changes status without yanking the plan, and `customer.subscription.deleted` correctly downgrades to Free.

**Two real bugs found and fixed during this verification**, not before it:
- Dead code: `PRICE_ID_TO_PLAN`/`_price_id_map()` was written but never called (the webhook handler correctly reads `target_plan` from checkout metadata instead) — removed rather than left as confusing clutter.
- A non-UUID (or otherwise malformed) `org_id` in webhook data crashed with a raw, unhandled database driver exception instead of failing gracefully — found by testing exactly that edge case, fixed with an explicit UUID-shape check before ever touching the database.

**Still open**: this needs a real Stripe merchant account, real Price IDs
in the dashboard, and the webhook URL registered there before any of
this processes a real payment. No amount of code changes that.

## Security audit this pass — one serious bug found and fixed, two hardening gaps closed

Did a real audit for the three things asked about: SQL injection, plan-
limit bypass ("unlimited" usage), and cross-tenant data leaks. Results:

### 1. SQL injection — audited, none found
Grepped the entire backend for raw string-interpolated SQL. Every query
in the app's own code goes through the SQLAlchemy ORM (`select()`/
`.where()`), which parameterizes automatically. The one place raw SQL
text exists at all is the user-facing `database.query`/`database.execute`
nodes (`integrations/database/handler.py`) — already using
`text(sql).bindparams()` with the user's own bind parameters, already
verified against a live SQL-injection-shaped payload in an earlier pass
(a `'; DROP TABLE ...` string as a bound parameter matched 0 rows,
table stayed intact).

### 2. Cross-tenant credential access — SERIOUS bug found, fixed, verified with a real attack
`get_credential_data()`/`get_access_token()` (`oauth/flow.py`) decrypted
**any** credential by ID alone — there was no check that the workflow
executing it actually belonged to the credential's owner. Every
integration handler (all ~25 of them) trusted `credential_id` from the
node config at face value.

**What this meant in practice**: a workflow could reference any
credential UUID in the whole database — guessed, leaked via a log,
inherited from a duplicated workflow after leaving an org — and the
engine would decrypt and use someone else's Stripe key, database
password, or Slack token on that workflow's behalf.

**Fix**: `core/execution_engine.py`'s `_execute_node` (the single choke
point every node execution passes through, regardless of integration)
now verifies the credential's owner matches the executing workflow's
owner before ever calling a handler — fixed in one place rather than 25
individual integration files, so it can't be forgotten in the 26th.

**Verified with a real attack simulation**, not just a unit test: built
an actual attacker workflow referencing a real victim credential ID, ran
it through the real `execute_workflow()` — confirmed it fails with
"does not belong to this workflow's owner" before the credential is ever
decrypted. Then confirmed the legitimate case (owner using their own
credential) passes the check fine and only fails later for an unrelated
reason (test used fake ciphertext).

Every other route (workflows, credentials, executions — get/update/
delete) was already correctly scoped by `owner_id`/`user_id` — this was
specifically a gap in the internal execution path, not the API routes.

### 3. Plan-limit race condition — found via real concurrency testing, fixed
The active-workflow and execution limit checks (`core/plans.py`) did a
COUNT-then-compare with no locking — under concurrent requests near the
boundary, several could all read "under limit" before any of them
committed, overshooting the cap.

First fix attempt (`SELECT ... FOR UPDATE` on the org row) was tried,
then tested under real concurrency — and **deadlocked**: any ordinary
insert referencing the org (a new workflow, a new execution) takes an
implicit lock on that row for its foreign-key check, and two concurrent
transactions each holding their own insert's lock while waiting for the
other's `FOR UPDATE` produced a genuine `DeadlockDetectedError`, caught
live, not theorized.

**Real fix**: switched to a Postgres advisory lock
(`pg_advisory_xact_lock(hashtext(org_id))`), which serializes concurrent
limit checks for the same org without ever contending with ordinary
row locks. **Verified by firing 10 real concurrent activation attempts**
at an org sitting one below its plan's limit: exactly 1 succeeded, 9
were correctly blocked, zero deadlocks, zero errors, final count landed
exactly at the plan's limit — not over.

**Also closed**: `check_user_limit` (member invites) now uses the same
advisory-lock pattern for consistency — same race in principle, lower
real-world likelihood (invites are inherently rarer than workflow
activations or executions), closed anyway rather than left as a known gap.
